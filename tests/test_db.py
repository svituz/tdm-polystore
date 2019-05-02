# FIXME: We are assuming that we have access to the DB mentioned in conftest.py

# FIXME move to fixtures
import os
import json
root = os.path.dirname(os.path.abspath(__file__))
sensor_types_fname = os.path.join(root, 'data/sensor_types.json')
sensors_fname = os.path.join(root, 'data/sensors.json')


def test_init_db(runner):
    result = runner.invoke(args=['db', 'init'])
    assert 'Initialized' in result.output


def test_load_db(runner):
    # FIXME it assumes that it will be run after test_init_db
    result = runner.invoke(args=['db', 'load', sensor_types_fname])
    n = len(json.load(open(sensor_types_fname))['sensor_types'])
    assert "Loaded {'sensor_types': %d}" % n in result.output
    result = runner.invoke(args=['db', 'load', sensors_fname])
    n = len(json.load(open(sensors_fname))['sensors'])
    assert "Loaded {'sensors': %d}" % n in result.output
