# imo-vmdb

This project provides a command line tool to maintain a SQL interface to the
[Visual Meteor Database (VMDB)](https://www.imo.net/members/imo_vmdb/)
of the
[International Meteor Organization (IMO)](https://www.imo.net/).

The IMO provides the data in the form of pure text files [(CSV files)](https://en.wikipedia.org/wiki/Comma-separated_values).
This format is not suitable for the evaluation of this data.
With *imo-vmdb* this data is imported into a relational SQL database.
A large number of programming languages have interfaces to these databases.
This makes it possible to load data from the VMDB according to different criteria in different applications.

No evaluations can be performed with *imo-vmdb* itself.
However, during the import of the data, various error and plausibility checks are performed.
This ensures that the data are suitable for analysis.
In addition, the observations are supplemented with properties in order to be able to filter according to these properties.
Examples are the positions of the radiants, the sun and the moon.

For more information see https://imo-vmdb.readthedocs.io/en/latest/
.
