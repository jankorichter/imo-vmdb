from datetime import datetime

from astropy import units as u
from astropy.coordinates import EarthLocation

from imo_vmdb.db import DBException


class NormalizerException(Exception):
    """Raised when a normalised record cannot be written (e.g. radiant below horizon)."""


class BaseRecord:
    """Shared fields for a single imported observation (rate or magnitude).

    Parses and exposes the observation window, session and observer IDs, and
    the observer's geographic location.  Equality and containment operators
    implement time-period overlap semantics used for deduplication during
    normalisation.

    :param record: Dict of raw database columns as returned by the import query.
    """

    def __init__(self, record):
        self.id = record["id"]
        self.shower = record["shower"]
        self.session_id = record["session_id"]
        self.observer_id = record["observer_id"]
        self.session_observer_id = record["session_observer_id"]
        self.loc = EarthLocation(
            lat=record["latitude"] * u.deg, lon=record["longitude"] * u.deg
        )

        if isinstance(record["start"], datetime):
            self.start = record["start"]
        else:
            self.start = datetime.strptime(record["start"], "%Y-%m-%d %H:%M:%S")

        if isinstance(record["end"], datetime):
            self.end = record["end"]
        else:
            self.end = datetime.strptime(record["end"], "%Y-%m-%d %H:%M:%S")

    def __eq__(self, other):
        """Return ``True`` if the observations overlap (same session, same shower, intersecting periods).

        :param other: Another :class:`BaseRecord` to compare against.
        :return: ``True`` if the two records overlap, ``False`` otherwise.
        """
        return not self != other

    def __ne__(self, other):
        """Return ``True`` if the observations do not overlap.

        :param other: Another :class:`BaseRecord` to compare against.
        :return: ``True`` if the records differ in session, shower, or have
            non-overlapping time periods.
        """
        if self.session_id != other.session_id:
            return True

        if self.shower != other.shower:
            return True

        if self.end <= other.start:
            return True

        if self.start >= other.end:
            return True

        return False

    def __contains__(self, other):
        """Return ``True`` if *other*'s time period is fully contained within this observation's period.

        :param other: Another :class:`BaseRecord` to compare against.
        :return: ``True`` if *other* overlaps this record and its period falls
            entirely within this record's period.
        """
        if self != other:
            return False

        if self.start > other.start or self.end < other.end:
            return False

        return True


class BaseNormalizer:
    """Base class for normalisation passes.

    Tracks read/write/discard counters and provides error-logging helpers.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :param logger: Logger for error messages.
    """

    def __init__(self, db_conn, logger):
        self._db_conn = db_conn
        self._logger = logger
        self.has_errors = False
        self.counter_read = 0
        self.counter_write = 0
        self.counter_discard = 0

    def _log_error(self, msg):
        """Log *msg* as an error and set :attr:`has_errors`.

        :param msg: Error message string.
        """
        self._logger.error(msg)
        self.has_errors = True

    def _log_discard(self, session_id, obs_id, reason):
        """Log that an observation was discarded and increment :attr:`counter_discard`.

        :param session_id: Session ID used in the log message.
        :param obs_id: Observation ID used in the log message.
        :param reason: Human-readable reason for discarding the record.
        """
        self._logger.error(
            "session %s: observation %s discarded - %s" % (session_id, obs_id, reason)
        )
        self.counter_discard += 1
        self.has_errors = True


def create_rate_magn(db_conn):
    """Link rate observations to their corresponding magnitude observations.

    Populates the ``rate_magnitude`` table by matching rate and magnitude
    records that share the same session and shower and whose time periods are
    equal or where the magnitude period fully contains the rate period.  Each
    rate may be linked to at most one magnitude record.  Also computes the
    effective limiting magnitude for each magnitude record as the
    t_eff-weighted mean of the linked rate limiting magnitudes.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :raises DBException: On any database error.
    """
    try:
        cur = db_conn.cursor()
        # find magnitude-rate-pairs containing each other
        cur.execute(
            db_conn._convert_stmt("""
            WITH selection AS (
                SELECT
                    r.id as rate_id,
                    m.id as magn_id,
                    r.period_start as rate_period_start,
                    r.period_end as rate_period_end,
                    m.period_start as magn_period_start,
                    m.period_end as magn_period_end,
                    r.freq as rate_n,
                    m.freq as magn_n
                FROM rate as r
                INNER JOIN magnitude as m
                    ON
                       r.session_id = m.session_id AND
                       (
                           r.shower = m.shower OR
                           (r.shower IS NULL AND m.shower IS NULL)
                       )
            ),
            rate_magnitude_rel AS (
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    true as "equals"
                FROM selection
                WHERE
                   rate_period_start = magn_period_start AND
                   rate_period_end = magn_period_end
                UNION
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    false as "equals"
                FROM selection
                WHERE
                    -- magnitude period contains rate period
                    rate_period_start BETWEEN magn_period_start AND magn_period_end AND
                    rate_period_end BETWEEN magn_period_start AND magn_period_end AND
                    NOT (
                        -- rate period contains magnitude period
                        magn_period_start BETWEEN rate_period_start AND rate_period_end AND
                        magn_period_end BETWEEN rate_period_start AND rate_period_end
                    )
            ),
            aggregates AS (
                SELECT
                    rate_id,
                    magn_id,
                    sum(rate_n) OVER (PARTITION BY magn_id) as rate_n,
                    magn_n,
                    "equals",
                    count(magn_id) OVER (PARTITION BY rate_id) as magn_id_count
                FROM rate_magnitude_rel
            ),
            unique_rate_ids AS (
                SELECT
                    rate_id,
                    magn_id,
                    "equals"
                FROM aggregates
                WHERE
                    magn_id_count = 1 AND
                    rate_n >= magn_n
            )

            SELECT rate_id, magn_id, "equals" FROM unique_rate_ids
        """)
        )
    except Exception as e:
        raise DBException(str(e))

    column_names = [desc[0] for desc in cur.description]
    delete_stmt = db_conn._convert_stmt(
        "DELETE FROM rate_magnitude WHERE rate_id = %(rate_id)s"
    )
    insert_stmt = db_conn._convert_stmt("""
        INSERT INTO rate_magnitude (
            rate_id,
            magn_id,
            "equals"
        ) VALUES (
            %(rate_id)s,
            %(magn_id)s,
            %(equals)s
        )
    """)

    try:
        write_cur = db_conn.cursor()
    except Exception as e:
        raise DBException(str(e))

    for record in cur:
        record = dict(zip(column_names, record, strict=False))
        magn_rate = {
            "rate_id": record["rate_id"],
            "magn_id": record["magn_id"],
            "equals": record["equals"],
        }
        try:
            write_cur.execute(delete_stmt, {"rate_id": record["rate_id"]})
            write_cur.execute(insert_stmt, magn_rate)
        except Exception as e:
            raise DBException(str(e))

    # set limiting magnitude
    try:
        cur.execute(db_conn._convert_stmt("UPDATE magnitude SET lim_magn = NULL"))
        cur.execute(
            db_conn._convert_stmt("""
            WITH limiting_magnitudes AS (
                SELECT rm.magn_id, sum(r.freq) as freq, sum(r.freq*r.lim_magn) as lim_magn_sum
                FROM rate r
                INNER JOIN rate_magnitude rm ON rm.rate_id = r.id
                GROUP BY rm.magn_id
            )
            SELECT magn_id, freq, lim_magn_sum
            FROM limiting_magnitudes
        """)
        )
    except Exception as e:
        raise DBException(str(e))

    column_names = [desc[0] for desc in cur.description]
    update_stmt = db_conn._convert_stmt(
        "UPDATE magnitude SET lim_magn = %(lim_magn)s WHERE id = %(magn_id)s"
    )
    for record in cur:
        record = dict(zip(column_names, record, strict=False))

        if record["freq"] > 0:
            lim_magn = record["lim_magn_sum"] / record["freq"]
            lim_magn = round(lim_magn, 2)

            try:
                write_cur.execute(
                    update_stmt,
                    {"lim_magn": lim_magn, "magn_id": record["magn_id"]},
                )
            except Exception as e:
                raise DBException(str(e))

    try:
        write_cur.close()
        cur.close()
    except Exception as e:
        raise DBException(str(e))
