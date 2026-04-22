"""Tests for the REST API (/api/v1/*)."""


class TestShowers:
    def test_returns_list(self, client):
        r = client.get('/api/v1/showers')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_response_has_expected_fields(self, client):
        r = client.get('/api/v1/showers')
        shower = r.get_json()[0]
        for field in ('iau_code', 'name', 'start_month', 'start_day', 'end_month', 'end_day'):
            assert field in shower


class TestRates:
    def test_returns_200_with_empty_observations(self, client):
        r = client.get('/api/v1/rates')
        assert r.status_code == 200
        data = r.get_json()
        assert 'observations' in data
        assert isinstance(data['observations'], list)

    def test_shower_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?shower=PER')
        assert r.status_code == 200

    def test_spo_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?shower=SPO')
        assert r.status_code == 200

    def test_multiple_shower_filter(self, client):
        r = client.get('/api/v1/rates?shower=PER&shower=GEM')
        assert r.status_code == 200

    def test_period_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?period_start=2020-01-01&period_end=2020-12-31')
        assert r.status_code == 200

    def test_sl_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?sl_min=130.0&sl_max=150.0')
        assert r.status_code == 200

    def test_lim_magn_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?lim_magn_min=5.0&lim_magn_max=7.0')
        assert r.status_code == 200

    def test_sun_alt_filter_returns_200(self, client):
        r = client.get('/api/v1/rates?sun_alt_max=-6.0')
        assert r.status_code == 200

    def test_invalid_sl_min_returns_400(self, client):
        r = client.get('/api/v1/rates?sl_min=notanumber')
        assert r.status_code == 400
        assert 'error' in r.get_json()

    def test_invalid_lim_magn_returns_400(self, client):
        r = client.get('/api/v1/rates?lim_magn_min=bad')
        assert r.status_code == 400

    def test_include_sessions_key_present(self, client):
        r = client.get('/api/v1/rates?include=sessions')
        assert r.status_code == 200
        assert 'sessions' in r.get_json()

    def test_include_magnitudes_key_present(self, client):
        r = client.get('/api/v1/rates?include=magnitudes')
        assert r.status_code == 200
        assert 'magnitudes' in r.get_json()


class TestMagnitudes:
    def test_returns_200_with_empty_observations(self, client):
        r = client.get('/api/v1/magnitudes')
        assert r.status_code == 200
        data = r.get_json()
        assert 'observations' in data

    def test_shower_filter_returns_200(self, client):
        r = client.get('/api/v1/magnitudes?shower=PER')
        assert r.status_code == 200

    def test_invalid_param_returns_400(self, client):
        r = client.get('/api/v1/magnitudes?lim_magn_min=bad')
        assert r.status_code == 400

    def test_include_sessions_key_present(self, client):
        r = client.get('/api/v1/magnitudes?include=sessions')
        assert r.status_code == 200
        assert 'sessions' in r.get_json()


class TestOpenApiSpec:
    def test_yaml_is_reachable(self, client):
        r = client.get('/api/v1/openapi.yaml')
        assert r.status_code == 200
        assert b'openapi' in r.data

    def test_content_type_is_yaml(self, client):
        r = client.get('/api/v1/openapi.yaml')
        assert 'yaml' in r.content_type
