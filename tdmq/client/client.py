import requests
import tiledb
import os
import numpy as np

# FIXME build a better logging infrastructure
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.info('Logging is active.')

from tdmq.client.sources import ScalarSource

source_classes = {
    ('Station', 'PointWeatherObserver'): ScalarSource,
}


class Client:
    TILEDB_HDFS_ROOT = 'hdfs://hdfs:9000/arrays'
    TDMQ_BASE_URL = 'http://web:8000/api/v0.0'

    def __init__(self,
                 tdmq_base_url=None, tiledb_ctx=None, tiledb_hdfs_root=None):
        self.base_url = self.TDMQ_BASE_URL \
            if tdmq_base_url is None else tdmq_base_url
        self.tiledb_hdfs_root = self.TILEDB_HDFS_ROOT \
            if tiledb_hdfs_root is None else tiledb_hdfs_root
        self.tiledb_ctx = tiledb_ctx
        self.managed_objects = {}

    def _destroy_source(self, tdmq_id):
        r = requests.delete(f'{self.base_url}/sources/{tdmq_id}')
        if r.status_code == 500:
            raise ValueError('Internal error')

    def _source_data_path(self, tdmq_id):
        return os.path.join(self.tiledb_hdfs_root, tdmq_id)

    def _register_thing(self, thing, description):
        assert isinstance(description, dict)
        r = requests.post(f'{self.base_url}/{thing}', json=[description])
        if r.status_code == 500:
            raise ValueError('Internal error')
        description['tdmq_id'] = r.json()[0]
        return description

    def deregister_source(self, s):
        if s in self.managed_objects:
            self._destroy_source(s.tdmq_id)
            del self.managed_objects[s.tmdq_id]
            del s
        else:
            # NO-OP
            pass

    def register_source(self, description, nslots=None):
        """Register a new data source
        .. :quickref: Register a new data source
        """
        description = self.register_thing('sources', description)
        if 'shape' in description and len(description['shape']) > 0:
            assert nslots is not None
            try:
                self._create_tiledb_array(nslots, description)
            except Exception as e:
                logger.error(
                    f'Failure in creating tiledb array: {e}, cleaning up')
                self._destroy_source(description['tdmq_id'])
        return self.get_source_proxy(description['tmdq_id'])

    def get_entity_categories(self):
        return requests.get(f'{self.base_url}/entity_categories').json()

    def get_entity_types(self):
        return requests.get(f'{self.base_url}/entity_types').json()

    def get_geometry_types(self):
        return requests.get(f'{self.base_url}/geometry_types').json()

    def get_sources(self, args):
        res = requests.get(f'{self.base_url}/sources', params=args).json()
        return [self.get_source_proxy(r['tdmq_id']) for r in res]

    def get_source_proxy(self, tdmq_id):
        res = requests.get(f'{self.base_url}/sources/{tdmq_id}').json()
        assert res['tdmq_id'] == tdmq_id
        # FIXME we need to fix this 'type' thing
        scat = res['category']
        stype = res['type']
        s = source_classes[(scat, stype)](self, tdmq_id, stype, res)
        self.managed_objects[s.tdmq_id] = s
        return s

    def get_timeseries(self, code, args):
        return requests.get(f'{self.base_url}/sources/{code}/timeseries',
                            params=args).json()

    def fetch_data_block(self, block_of_refs, args):
        urls = set(r[0] for r in block_of_refs)
        # FIXME we support only trivial cases, for the time being
        assert len(urls) == 1
        indices = np.array([r[1] for r in block_of_refs], dtype=np.int32)
        assert len(indices) == 1 or np.all(indices[1:] - indices[:-1] == 1)
        url = urls.pop()
        if isinstance(args[0], slice):
            args = (slice(int(indices.min()),
                          int(indices.max()) + 1), ) + args[1:]
        else:
            assert len(indices) == 1
            args = (int(indices[0]),) + args[1:]
        with tiledb.DenseArray(url, mode='r', ctx=self.tiledb_ctx) as A:
            data = A[args]
        return data

    def _create_tiledb_array(self, n_slots, description):
        array_name = self.sensor_data_path(description['code'])
        if tiledb.object_type(array_name) is not None:
            raise ValueError('duplicate object with path %s' % array_name)
        shape = description['shape']
        assert len(shape) > 0 and n_slots > 0
        dims = [tiledb.Dim(name="delta_t",
                           domain=(0, n_slots),
                           tile=1, dtype=np.int32)]
        dims = dims + [tiledb.Dim(name=f"dim{i}", domain=(0, n - 1),
                                  tile=n, dtype=np.int32)
                       for i, n in enumerate(shape)]
        dom = tiledb.Domain(*dims, ctx=self.tiledb_ctx)
        attrs = [tiledb.Attr(name=aname, dtype=np.float32)
                 for aname in description['controlledProperty']]
        schema = tiledb.ArraySchema(domain=dom, sparse=False,
                                    attrs=attrs, ctx=self.tiledb_ctx)
        # Create the (empty) array on disk.
        tiledb.DenseArray.create(array_name, schema)
        return array_name

    def register_measure(self, measure):
        assert isinstance(measure, dict)
        # FIXME check if thing already exists and manage errors
        r = requests.post(f'{self.base_url}/measures', json=[measure])
        if r.status_code == 500:
            raise ValueError('Illegal value')
        return r.json()

    def register_sensor_type(self, description):
        description = self.register_thing('sensor_types', description)
        self.update_sensor_types()
        return description

