import pytest

from pipelines.collectors.open_meteo.points import build_points, haversine_km


def test_known_distance_and_exact_threshold():
    distance = haversine_km(38.7223, -9.1393, 41.1579, -8.6291)
    assert distance == pytest.approx(274, abs=1)
    assert haversine_km(38, -9, 38, -9) == 0
    state = {'requested_lat': 38.7223, 'requested_lon': -9.1393, 'returned_lat': 41.1579,
             'returned_lon': -8.6291, 'elevation_m': 0, 'timezone': 'Europe/Lisbon', 'run_id': 'run'}
    frame = build_points({'0001': state}, {'point_divergence_km': distance})
    assert not frame.iloc[0].diverged and frame.iloc[0].elevation_m == 0
    frame = build_points({'0001': state}, {'point_divergence_km': distance - .01})
    assert frame.iloc[0].diverged
