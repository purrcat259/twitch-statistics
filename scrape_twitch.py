import csv
import os
import time
from datetime import datetime
from shutil import move as move_file
from cfg import SCP_COMMAND, EMAIL_COMMAND
from consolidate_data import consolidate_all_data
from collection import twitchapi
from logging import FileHandler

cycle_delay = 30  # seconds

config_values = [
    {
        'url_name': 'Elite:%20Dangerous',
        'full_name': ['Elite: Dangerous', 'Elite Dangerous'],
        'shorthand': 'ED'
    },
    {
        'url_name': 'Planet%20Coaster',
        'full_name': ['Planet Coaster', 'Planet: Coaster'],
        'shorthand': 'PC'
    },
]


def pause(amount=5):
    for pause_tick in range(amount, 0, -1):
        print('[+] Paused for {} seconds   '.format(pause_tick), end='\r')
        time.sleep(1)
    print('                                    ', end='\r')


def insert_data_rows_into_csv(file_name=None, data_rows=None, verbose=False):
    if file_name is None:
        if verbose:
            print('[-] No file name given to write to as a CSV file!')
    elif data_rows is None:
        if verbose:
            print('[-] No data rows provided to write to CSV!')
    else:
        file_name += '.csv'  # append the format to the file name
        with open(file_name, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile, quotechar='"')
            for row in data_rows:
                writer.writerow(row)
            csvfile.flush()
            if verbose:
                print('[+] Successfully wrote {} rows to {}'.format(len(data_rows), file_name))


def consolidate_data(game_dicts, previous_date_string):
    print('[+] Starting consolidation procedure')
    notification_string = ''
    for game in game_dicts:
        file_name = game['short'] + '_' + previous_date_string + '.csv'
        try:
            # gather information for the backup notification
            file_size = os.path.getsize(file_name)
            file_size = round(file_size / (1024 * 1024), 2)
            notification_string += '{}: {}MB. '.format(game['name'], file_size)
            if perform_backup:
                print('[!] Running backup command')
                os.system(SCP_COMMAND.format(file_name, game['short']))
            else:
                print('[!] Not running backup command')
            # move the file to its respective data directory for consolidation
            data_folder = os.path.join(os.getcwd(), 'data', game['short'], 'csv', file_name)
            move_file(src=file_name, dst=data_folder)
        except Exception as e:
            print('[-] Backing up error: {}'.format(e))
            notification_string += 'NOT FINISHED. '
        time.sleep(1)
        if not perform_db_consolidation:
            print('[!] Not running db consolidation')
            #print('[!] Moving CSVs to complete folder')
            #move_file(
            #    src=os.path.join(os.getcwd(), 'data', game['short'], 'csv', file_name),
            #    dst=os.path.join(os.getcwd(), 'completed', file_name)
            #)
    if perform_db_consolidation:
        print('[!] Starting Database consolidation')
        try:
            consolidate_all_data(game_shorthands=[game['short'] for game in game_dicts])
            notification_string += '\nConsolidation of files completed successfully'
        except Exception as e:
            print('[-] Consolidation error: {}'.format(e))
            notification_string += '\nConsolidation of files did not complete successfully'
    if send_notification_email:
        print('[!] Sending notification email')
        os.system(EMAIL_COMMAND.format(notification_string))
    else:
        print('[!] Not sending notification email. Notification string:')
        print(notification_string)
    pause(2)
    """
    from consolidation import get_info
    # run the get info object
    # CURRENTLY DISABLED DUE TO LACK OF VPS RESOURCES
    for game in game_dicts:
        output = get_info.TwitchStatisticsOutput(game_name=game['name'],
                                        game_shorthand=game['short'],
                                        db_mid_directory='',
                                        verbose=True)
        output.run()
    """


def get_current_date_string():
    previous_day, previous_month, previous_year = datetime.now().day, datetime.now().month, datetime.now().year
    return '{}_{}_{}'.format(previous_day, previous_month, previous_year)


def log_downtime():
    handler = FileHandler(downtime_log_path, mode='a')
    handler.emit('downtime|{}\n'.format(time.time()))
    handler.close()


def main():
    games = get_config_values()
    previous_day = datetime.now().day
    previous_date_string = get_current_date_string()
    while True:
        # check if a day has passed
        day = datetime.now().day
        current_date_string = get_current_date_string()
        # if a day has finished, then make a backup
        if not day == previous_day:
            # update the previous day number. No need to compare the month/year too
            previous_day = day
            # run consolidation procedure
            consolidate_data(game_dicts=games, previous_date_string=previous_date_string)
            # update the date string
            previous_date_string = current_date_string
        # for each game, get the data
        for game_name in games:
            print('[+] Starting cycle for: {}'.format(game_name['full']))
            # Get the data for the current game by invoking the twitchapi module
            api = twitchapi.APIStreamsRequest(game_url_name=game_name['url'], game_proper_name=game_name['full'])
            try:
                api.request_all_game_data()
            except Exception as e:
                print(e)
                time.sleep(10)
                # move onto the next game
                break
            # if the last request was not successful, log to the error log
            if not api.last_request_successful():
                log_downtime()
            returned_data = api.return_required_data()
            # if any returned data is available, then write to to the CSV
            if returned_data is not None and len(returned_data) > 0:
                file_name = game_name['short'] + '_' + current_date_string
                insert_data_rows_into_csv(
                    file_name=file_name,
                    data_rows=returned_data,
                    verbose=True)
            else:
                print('[-] No rows written for: {}'.format(game_name['full']))
        pause(cycle_delay)

if __name__ == '__main__':
    main()
