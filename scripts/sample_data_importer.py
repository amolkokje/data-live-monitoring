import random
from influxdb_importer import InfluxdbImporter


class SampleDataImporter(InfluxdbImporter):
    """
    Sample data importer class which generates random data for the sake of demo
    """

    def __init__(self):
        """
        constructor
        """
        super(SampleDataImporter, self).__init__(database_name='Sample_Database',
                                                 tags_dict={'Sample_Tag': 'Sample_Tag_Value'},
                                                 data_importer_callback_list=[self.get_sample_data])

    def get_sample_data(self):
        """
        generates some random sample data for the demo
        :return: returns a tuple containing (measurement, dict containing data)
        """
        return 'sample_measurement', {'low_val': random.randint(10, 50),
                                      'medium_val': random.randint(50, 100),
                                      'high_val': random.randint(100, 150),
                                      }
