import os
import csv
import time
import datetime
from tqdm import tqdm
from pprint import pprint
from shutil import copy2 as copy_file
from neopysqlite.neopysqlite import Pysqlite


def calculate_average_from_list(data_list):
    # avoid division by zero
    if len(data_list) == 0:
        return 0
    # convert the data list to ints
    data_list = [int(data) for data in data_list]
    return sum(data_list) // len(data_list)


class StreamerDB:
    def __init__(self, game, streamer_name, stream_dicts):
        self.path = os.path.join(os.getcwd(), 'data', game, 'streamers', '{}.db'.format(streamer_name))
        self.game = game
        self.streamer_name = streamer_name
        self.next_stream_count = 0
        if self.db_exists():
            self.db = Pysqlite('{} {} Stream Database'.format(game, streamer_name), self.path, verbose=False)
        else:
            self.create_db()
            self.db = Pysqlite('{} {} Stream Database'.format(game, streamer_name), self.path, verbose=False)
            # This means that the overview and the streams table need to be created
            self.create_streams_table()
            self.create_overview_table()
            self.next_stream_count = len(self.db.get_table_names()) - 3
        self.last_stream_stored = len(self.db.get_table_names()) - 3
        self.stream_dicts = stream_dicts

    def run(self):
        self.import_csv_data()
        self.generate_overview_for_all_streams()

    def db_exists(self):
        return os.path.isfile(self.path)

    def create_db(self):
        if not self.db_exists():
            print('Database for {} does not exist. Creating DB now.'.format(self.streamer_name))
            copy_file(
                src=os.path.join(os.getcwd(), 'data', self.game, 'streamers', 'base', 'test_streamer.db'),
                dst=self.path
            )
        else:
            print('Database for {} already exists'.format(self.streamer_name))

    def create_overview_table(self):
        print('Creating the overview table for: {}'.format(self.streamer_name))
        time.sleep(1)
        create_statement = 'CREATE TABLE `overview` (`id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,' \
                           '`timestamp`	TEXT NOT NULL,' \
                           '`viewers_average` INTEGER NOT NULL,' \
                           '`viewers_peak` INTEGER NOT NULL,' \
                           '`followers`	INTEGER NOT NULL,' \
                           '`average_time_streamed`	INTEGER,' \
                           '`total_time_streamed`	INTEGER NOT NULL,' \
                           '`partnership`	INTEGER NOT NULL DEFAULT 0);'
        self.db.execute_sql(create_statement)

    def create_streams_table(self):
        print('Creating the streams table for: {}'.format(self.streamer_name))
        time.sleep(1)
        create_statement = 'CREATE TABLE `streams` (`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, ' \
                           '`timestamp`	TEXT NOT NULL, `duration` INTEGER NOT NULL, `viewers_average` ' \
                           'INTEGER NOT NULL, `viewers_peak` INTEGER NOT NULL, `follower_increase` INTEGER NOT NULL)'
        self.db.execute_sql(create_statement)

    def create_stream_table(self):
        print('Creating stream_{} table for: {}'.format(self.next_stream_count, self.streamer_name))
        time.sleep(1)
        create_statement = 'CREATE TABLE "stream_{}" (`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,' \
                           '`timestamp`	TEXT NOT NULL, `viewers` INTEGER NOT NULL, `followers` INTEGER NOT NULL, ' \
                           '`partnership`INTEGER NOT NULL DEFAULT 0)'.format(self.next_stream_count)
        self.db.execute_sql(create_statement)

    def import_csv_data(self):
        print('Importing CSV data into stream tables for: {}'.format(self.streamer_name))
        for stream_dict in self.stream_dicts:
            # create a table for each CSV
            self.create_stream_table()
            # CSV schema is NAME, VIEWERS, FOLLOWERS, PARTNERSHIP, TIMESTAMP
            # DB schema is ID, TIMESTAMP, VIEWERS, FOLLOWERS, PARTNERSHIP
            raw_data_list = stream_dict['raw_data']
            fixed_schema_list = [[row[4], row[1], row[2], row[3]] for row in raw_data_list]
            for row in tqdm(fixed_schema_list):
                self.db.insert_row(
                    table='stream_{}'.format(self.next_stream_count),
                    row_string='(NULL, ?, ?, ?, ?)',
                    row_data=row)
            # generate a stream data row for the streams table
            self.generate_stream_data_row(stream_dict=stream_dict)
            # iterate the stream counter
            self.next_stream_count += 1
        # update the number of streams stored
        self.last_stream_stored = len(self.db.get_table_names()) - 3

    def generate_stream_data_row(self, stream_dict):
        print('Generating stream overview')
        # Streams table schema:
        # ID, Date + start time, duration (seconds), average viewership, peak viewership, follower differential
        timestamp = stream_dict['start_timestamp']
        duration = stream_dict['duration']
        viewers_list = [row[1] for row in stream_dict['raw_data']]
        viewers_average = calculate_average_from_list(viewers_list)
        viewers_peak = max(viewers_list)
        # last follower count - first follower count
        follower_delta = int(stream_dict['raw_data'][-1][2]) - int(stream_dict['raw_data'][0][2])
        self.db.insert_row(
            table='streams',
            row_string='(NULL, ?, ?, ?, ?, ?)',
            row_data=[timestamp, duration, viewers_average, viewers_peak, follower_delta]
        )

    def generate_overview_for_all_streams(self):
        print('Generating overview for all streams so far')
        # Streams table schema:
        # ID, Date + start time, duration (seconds), average viewership, peak viewership, follower differential
        data = self.db.get_all_rows('streams')
        # get the duration data
        durations = [int(field[2]) for field in data]
        total_duration = sum(durations)
        total_average_duration = calculate_average_from_list(durations)
        # get the viewer data
        average_viewers_list = [int(field[3]) for field in data]
        total_average_viewers = calculate_average_from_list(average_viewers_list)
        peak_viewers_list = [int(field[4]) for field in data]
        try:
            highest_peak_viewers = max(peak_viewers_list)
        except ValueError:
            highest_peak_viewers = 0
        # get the follower data from the latest stream table and not the overview data
        data = self.db.get_all_rows('stream_{}'.format(self.last_stream_stored - 1))
        last_follower_count = data[-1][3]
        # get last partnership data from the latest stream table too
        partnered = data[-1][4]
        # Overview table schema:
        # ID, CURRENT TIMESTAMP, AVERAGE VIEWERS, PEAK VIEWERS, FOLLOWERS, AVERAGE STREAM DURATION,
        # TOTAL STREAM DURATION, PARTNERSHIP
        self.db.insert_row(
            table='overview',
            row_string='(NULL, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)',
            row_data=[total_average_viewers, highest_peak_viewers, last_follower_count, total_average_duration, total_duration, partnered])


class GameDB:
    def __init__(self, game):
        self.path = os.path.join(os.getcwd(), 'data', game, '{}_data.db'.format(game))
        self.game = game
        if self.db_exists():
            self.db = Pysqlite('{} Stream Database'.format(game), self.path, verbose=False)
        else:
            self.create_db()
            self.db = Pysqlite('{} Stream Database'.format(game), self.path, verbose=False)
            # If the DB does not exist, then create the tables
            self.create_global_data_table()
            self.create_streamers_data_table()
            self.create_tier_bounds_table()
            self.create_tier_data_table()

    def run(self):
        pass

    def db_exists(self):
        return os.path.isfile(self.path)

    def create_db(self):
        if not self.db_exists():
            print('Database for the game: {} does not exist. Creating DB now.'.format(self.game))
            copy_file(
                src=os.path.join(os.getcwd(), 'data', 'base', 'test_game.db'),
                dst=self.path
            )
        else:
            print('Database for game: {} already exists'.format(self.game))

    def create_global_data_table(self):
        print('Creating global data table for: {}'.format(self.game))
        time.sleep(1)
        create_statement = 'CREATE TABLE `global_data` (`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, ' \
                           '`timestamp`	TEXT NOT NULL,' \
                           '`stream_count` INTEGER NOT NULL,' \
                           '`average_time_streamed` INTEGER NOT NULL,' \
                           '`total_time_streamed` INTEGER NOT NULL, ' \
                           '`longest_stream` INTEGER NOT NULL)'
        self.db.execute_sql(create_statement)

    def create_streamers_data_table(self):
        print('Creating streamers data table for: {}'.format(self.game))
        time.sleep(1)
        create_statement = 'CREATE TABLE `streamers_data` (`id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, ' \
                           '`viewers_average` INTEGER NOT NULL,' \
                           '`viewers_peak` INTEGER NOT NULL,' \
                           '`followers` INTEGER NOT NULL,' \
                           '`sream_count` INTEGER NOT NULL,' \
                           '`total_time_streamed` INTEGER NOT NULL,' \
                           '`percentage_duration` REAL NOT NULL,' \
                           '`partnership` INTEGER NOT NULL)'
        self.db.execute_sql(create_statement)

    def create_tier_bounds_table(self):
        print('Creating tier bounds table for: {}'.format(self.game))
        time.sleep(1)
        create_statement = 'CREATE TABLE "tier_bounds" (`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,' \
                           '`number` INTEGER NOT NULL, ' \
                           '`upper_bound` INTEGER NOT NULL, ' \
                           '`lower_bound` INTEGER NOT NULL)'
        time.sleep(1)
        tier_amount = int(input('Please enter the number of tiers that will be present: '))
        for i in range(0, tier_amount):
            i += 1
            print('BOUND NUMBERS ARE BOTH INCLUSIVE. FOR 100 TO 50, ENTER 100 AS UPPER AND 50 AS LOWER')
            upper_bound = int(input('Please enter the upper bound for tier {}'.format(i)))
            lower_bound = int(input('Please enter the lower bound for tier {}'.format(i)))
            self.db.insert_row(
                table='tier_bounds',
                row_string='(NULL, ?, ?, ?)',
                row_data=[i, upper_bound, lower_bound])
        self.db.execute_sql(create_statement)

    def create_tier_data_table(self):
        print('Creating tier data table for: {}'.format(self.game))
        time.sleep(1)
        create_statement = 'CREATE TABLE `tier_data` (`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, ' \
                           '`streamer_name`	TEXT NOT NULL, ' \
                           '`streamer_tier` INTEGER NOT NULL)'
        self.db.execute_sql(create_statement)

    def return_streamer_tier(self, average_viewers):
        bounds = self.db.get_all_rows('tier_bounds')
        for tier, upper, lower in bounds:
            if upper >= average_viewers >= lower:
                return tier
        else:
            return 0

    

# CSV SCHEMA:
# NAME, VIEWERS, FOLLOWERS, PARTNERSHIP, TIMESTAMP


def read_csv(file_path):
    data = []
    with open(file_path, newline='') as csvfile:
        csvreader = csv.reader(csvfile, quotechar='"')
        for row in csvreader:
            data.append(row)
    return data


def convert_timestamp_to_datetime(timestamp):
    # timestamp format: '2016-01-25 10:46:18'
    split_string = timestamp.split(' ')
    date_part = split_string[0].split('-')
    time_part = split_string[1].split(':')
    year, month, day = int(date_part[0]), int(date_part[1]), int(date_part[2])
    hour, minute, second = int(time_part[0]), int(time_part[1]), int(time_part[2])
    return datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)


def calculate_time_delta(timestamp_one, timestamp_two):
    time_delta = convert_timestamp_to_datetime(timestamp_two) - convert_timestamp_to_datetime(timestamp_one)
    # pprint(time_delta)
    return time_delta


# Split the raw stream data into a list of dicts with the stream data in each one
def split_by_stream(raw_stream_data):
    print('Splitting {} data rows by streams'.format(len(raw_stream_data)))
    # Pop the first field if the list length is odd
    if not len(raw_stream_data) % 2 == 0:
        raw_stream_data.pop(0)
    # the list to store the dictionaries in
    stream_dicts = []
    # a list to store the raw csv data in for that particular stream
    raw_data = []
    # a rolling number to store the duration in seconds of the stream
    for i, row in enumerate(raw_stream_data):
        end_found = False
        raw_data.append(row)
        time_field = row[4]
        if i+1 == len(raw_stream_data):  # avoid out of index exception
            print('End of CSV data found')
            end_found = True
        if not end_found:
            # get the next time field in the list
            next_time_field = raw_stream_data[i+1][4]
            # if the difference between the next time and the current time is greater than one hour,
            # then we will assume that it is a new stream
            time_delta = calculate_time_delta(time_field, next_time_field)
            # also stop if it is the last row in the list
        if time_delta.seconds / (60 * 60) > 1 or i == len(raw_stream_data) or end_found:
            # print('New stream detected, storing old one')
            print('[{}] Streamer {} held stream of duration {} seconds has {} rows and started at {}'.format(
                    len(stream_dicts),
                    raw_data[0][0],
                    calculate_time_delta(raw_data[0][4], raw_data[-1][4]).seconds,
                    len(raw_data),
                    raw_data[0][4]))
            data = {
                'id': len(stream_dicts),  # assign it an ID according to how many streams have been found
                'raw_data': raw_data,  # the list of raw CSV rows
                'duration': calculate_time_delta(raw_data[0][4], raw_data[-1][4]).seconds,
                'start_timestamp': raw_data[0][4]
            }
            # add the dict to the list
            stream_dicts.append(data)
            # reset the raw data
            raw_data = []
            # reset the duration
            continue  # continue to the next field to find the next stream
    return stream_dicts


def store_in_streamer_db(game, streamer, stream_dicts):
    s_db = StreamerDB(game=game, streamer_name=streamer, stream_dicts=stream_dicts)
    s_db.run()


def main():
    start_time = time.time()
    print('Starting consolidation script at {}'.format(datetime.datetime.fromtimestamp(start_time)))
    # For each game,
    games = [
        # 'ED',
        'PC'
    ]
    for game in games:
        print('Consolidation data for: {}'.format(game))
        # Get the paths of current CSVs
        csv_dir = os.path.join(os.getcwd(), 'data', game, 'csv')
        csv_files = os.listdir(csv_dir)
        # get all the data from the CSVs
        csv_data = []
        print('Opening {} CSV files:'.format(len(csv_files)))
        for csv_file in tqdm(csv_files):
            # print('Opening file: {}'.format(csv_file))
            data = read_csv(os.path.join(csv_dir, csv_file))
            csv_data.extend(data)
        # get only the streamer names from the csv data
        streamer_names = [row[0] for row in csv_data]
        # remove duplicates by converting it to a set and then back to a list
        streamer_names = list(set(streamer_names))
        # for each UNIQUE streamer name, store the raw CSV data into the next respective stream table
        # get the names of dbs already stored
        already_stored = os.listdir(os.path.join(os.getcwd(), 'data', game, 'streamers'))
        already_stored.remove('base')
        already_stored = [name.replace('.db', '') for name in already_stored]
        for streamer in streamer_names:
<<<<<<< HEAD
            # temporary skip through to find a streamer with a good set of data to test
            if not streamer == 'rammpppp':
=======
            if streamer in already_stored:
                print('Skipping: {}'.format(streamer))
>>>>>>> origin/new-db-structure
                continue
            # temporary skip through to find a streamer with a good set of data to test
            # if not streamer == 'spongietv':
            #     continue
            print('Processing data for: {}'.format(streamer))
            # get the data for just that streamer
            streamer_data = [row for row in csv_data if row[0] == streamer]
            stream_dicts = split_by_stream(streamer_data)
            if len(stream_dicts) == 0:
                continue
            store_in_streamer_db(game=game, streamer=streamer, stream_dicts=stream_dicts)
<<<<<<< HEAD
            break # remove this in final version
=======
            # break  # remove this in final version
>>>>>>> origin/new-db-structure
    finish_time = time.time()
    delta = (finish_time - start_time) // (60 * 60)
    print('Consolidation complete. Time taken: {} hours'.format(delta))


if __name__ == '__main__':
    main()
