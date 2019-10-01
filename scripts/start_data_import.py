from sample_data_importer import SampleDataImporter

if __name__ == '__main__':
    """
    This is the main() script which starts all the importers. Other importer threads can be initiliazed 
    and started here. 
    """
    SampleDataImporter().start_sampling_thread()
