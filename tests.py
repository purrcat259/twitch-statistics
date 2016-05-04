import os
import unittest
from import_csvs import CSVimport
from neopysqlite.neopysqlite import Pysqlite


class TestConfigFile(unittest.TestCase):
    def test_config_exists(self):
        self.assertTrue(expr=os.path.isfile('games.txt'), msg='Config file games.txt does not exists')

    def test_config_not_empty(self):
        with open('games.txt', 'r') as config:
            self.assertNotEqual(first=len(config.readlines()), second=0, msg='Config file is empty')

    def test_config_contents_amount(self):
        with open('games.txt', 'r') as config:
            self.assertEqual(first=len(config.readlines()) % 4, second=0, msg='Config file lines not multiple of 4')


class TestCSVImport(unittest.TestCase):
    def test_import_csv(self):
        c = CSVimport(games=['TEST'], db_mid_dir='data', delete_file=True, verbose=True)
        c.run()
        consolidated_db = Pysqlite(database_name='Consolidated DB', database_file=os.path.join(os.getcwd(), 'data', 'TEST_stats.db'), verbose=True)
        consolidated_streamers = consolidated_db.get_table_names()
        consolidated_data = []
        for streamer in consolidated_streamers:
            consolidated_data.append(consolidated_db.get_all_rows(table=streamer))
        complete_db = Pysqlite(database_name='Complete DB', database_file=os.path.join(os.getcwd(), 'data', 'TEST_stats_complete.db'), verbose=True)
        complete_streamers = complete_db.get_table_names()
        complete_data = []
        for streamer in complete_streamers:
            complete_data.append(complete_db.get_all_rows(table=streamer))
        self.assertEqual(first=consolidated_data, second=complete_data)

if __name__ == '__main__':
    unittest.main()