import logging
import sys
import time
import threading
import Queue
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

IMPORT_QUEUE_SIZE = 10000  # default max import queue size
SAMPLE_INTERVAL = 1  # default time interval between samples for sampling thread
IMPORT_RETRY = 3  # count to retry importing a collection of data points


class InfluxdbImportError(Exception):
    """
    Exception for InfluxdbImporter actions
    """
    pass


class InfluxdbImporter(object):
    """
    Base class for influxdb import
    """

    def __init__(self, database_name, tags_dict, data_importer_callback_list,
                 host='localhost', port=8086, username='admin', password='admin',
                 ignore_errors=True, import_queue_size=IMPORT_QUEUE_SIZE):
        """
        constructor initializes influxdb client, database and starts sampling and importing threads
        :param database_name: name of the influxdb database
        :param tags_dict: dict containing tags for the importer
        :param data_importer_callback_list: list containing callback list of data importers
        :param host: influxdb host dns/ip
        :param port: port on which influxdb service is running
        :param username: user name for influxdb
        :param password: password for influxdb
        :param ignore_errors: if True, ignore any errors from influxdb operations
        :param import_queue_size: max import queue size after which it does not get more data
        """
        self._database_name = database_name
        self._tags_dict = tags_dict
        self._data_importer_callback_list = data_importer_callback_list
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ignore_errors = ignore_errors

        # setup logging
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.setLevel(logging.DEBUG)
        self._log.addHandler(logging.StreamHandler(sys.stdout))

        # setup influxdb client, server
        self._influxdb_client = InfluxDBClient(host=host, port=port, username=username, password=password)
        # create unique database for importer
        self._create_database(database_name)

        # Initialize Queue, and start import thread
        # queue contains dicts, where each dict is a data sample
        self.sample_interval = SAMPLE_INTERVAL
        self._import_queue = Queue.Queue(maxsize=import_queue_size)
        self._is_import_thread_running = False
        self.start_importing_thread()

    def _create_database(self, name):
        """
        create database if it does not exist
        :param name: database name
        :return: None
        """
        database_list = [db['name'] for db in self._influxdb_client.get_list_database()]
        if name in database_list:
            self._log.info('Database with name {} already exists. Do not create a new database'.format(name))
        else:
            self._log.info('Creating database {}'.format(name))
            self._influxdb_client.create_database(name)
        self._influxdb_client.switch_database(name)

    def _enqueue_measurement(self, measurement, fields_dict):
        """
        Puts data in Queue for importing
        :param measurement: measurement name
        :param fields_dict: dict containing the data
        :return: None
        """
        self._import_queue.put({
            'measurement': measurement,
            'tags': self._tags_dict,
            'time': int(time.time() * 1000),
            'fields': fields_dict
        })

    def _import_data_list(self, data_list):
        """
        imports all the sampled data in the list
        :param data_list: list containing all the data points
        :return: None
        """
        self._log.info('Importing Data: {}'.format(data_list))
        import_count = 0
        ex_message = None
        while import_count < IMPORT_RETRY:
            try:
                if self._influxdb_client.write_points(data_list, time_precision='ms'):
                    return
            except InfluxDBClientError as ex:
                import_count += 1
                ex_message = str(ex)
        error_message = "Error when importing data to influxdb! Unable to import after {} retries. " \
                        "\nException=[{}] \nData=[{}]. " \
                        "\nEither the server is down or data is corrupted.".format(IMPORT_RETRY, ex_message, data_list)
        if self._ignore_errors:
            self._log.warn(error_message)
        else:
            raise InfluxdbImportError(error_message)

    def import_data(self, measurement, fields_dict):
        """
        enqueue the data to import with tags
        :param fields_dict: dict containing data sample
        :return: None
        """
        self._enqueue_measurement(measurement=measurement, fields_dict=fields_dict)

    def start_importing_thread(self):
        """
        Starts thread to pull from queue and import to influxdb
        :return: None
        """
        # flag to indicate that importing thread is running
        self._is_import_thread_running = True

        def import_thread():
            while self._is_import_thread_running:
                # empty the import queue if it contains data
                if not self._import_queue.empty():
                    # read the whole queue in a list
                    data_list = []
                    while not self._import_queue.empty():
                        data_list.append(self._import_queue.get())
                    # import all the data together in one batch
                    self._import_data_list(data_list)
                else:
                    # import queue is empty, wait for a moment before polling again
                    time.sleep(1)
            self._log.info('Importing stopped!')

        self._import_thread = threading.Thread(target=import_thread)
        self._import_thread.start()
        self._log.info('Importing started!')

    def stop_importing_thread(self):
        """
        Stop import thread
        :return: None
        """
        self._is_import_thread_running = False

    def start_sampling_thread(self, interval=None):
        """
        Default implementation goes through all the data importers and assumes that they will return dict containing
        data.
        NOTE: If some other mechanism is needed to get the data, this method can be overridden in the base class, or
        another util can be added to handle that
        :param interval: time interval between each sample
        :return: None
        """
        if interval:
            self.sample_interval = interval
        else:
            self.sample_interval = SAMPLE_INTERVAL

        while True:
            for data_importer_callback in self._data_importer_callback_list:
                measurement, fields_dict = data_importer_callback()
                self.import_data(measurement=measurement, fields_dict=fields_dict)
            time.sleep(self.sample_interval)
