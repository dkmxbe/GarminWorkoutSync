#!/usr/bin/env python3

import argparse
import logging
import os

#from clients.garminclient import GarminClient
from clients.garminapi import Garmin
from clients.icalclient import ICalClient

from models.workout import Workout
from models.schedule import Schedule

def command_dry(args):
    filename = "test_workouts/" + args.name + ".txt"
    # Read the contents of the test file
    if not os.path.isfile(filename):
        logging.error("Could not find the test file")
        return
    
    with open(filename) as f:
        w = Workout("test_workout", f.read())
        # print the json
        #w.create_workout()
        Workout.print_workout_json(w.create_workout())

def command_sync(args):
    logging.info("Syncing from google calendar")

    # Read calendar items for next 5 days
    cal_events = ICalClient.get_events(args.id, args.name)
    
    # Compare to online garmin workouts
    #with _garmin_client(args) as connection:
    connection = Garmin(email=args.username, password=args.password, is_cn=False, prompt_mfa=None)
    connection.login()

    # First we sync the workouts
    sync_workouts = {}
    existing_workouts_by_name = { Workout.extract_workout_name(w): w for w in connection.get_workouts() }

    try:
        today = ICalClient.get_today()
        existing_scheduled_workouts = {s.extract_item_workout(): s.extract_item_date() for s in Schedule.items(connection.get_schedule(today.year, today.month))}
        
        # Loop ics calendar items
        for cal_item in cal_events:
            w = Workout(cal_item.title, cal_item.description)

            workout_name = "T | %s - %s" % (w.get_workout_name(), cal_item.uid)
            local_workout = existing_workouts_by_name.get(workout_name)

            create_workout = True
            if local_workout:
                wid = Workout.extract_workout_id(local_workout)

                wid_exists = wid in existing_scheduled_workouts
                wid_is_updated = cal_item.is_changed()
                wid_is_new_date = wid_exists and existing_scheduled_workouts[wid] != cal_item.get_dt_start()
                if (not wid_exists or wid_is_updated or wid_is_new_date):
                    if (not wid_exists):
                        logging.info("The workout '%s' on '%s' does not exist in the current scheduled workout list" % (workout_name, cal_item.get_dt_start()))
                    elif (wid_is_updated):
                        logging.info("The workout '%s' on '%s' was updated since last run" % (workout_name, cal_item.get_dt_start()))
                    else:
                        logging.info("The workout '%s' on '%s' (old: '%s') was updated with a new date" % (workout_name, cal_item.get_dt_start(), existing_scheduled_workouts[wid]))
                    # Remove the workout on the garmin client. This way it is also removed from the schedule
                    logging.info("Deleting workout '%s' on '%s'" % (workout_name, existing_scheduled_workouts[wid]))
                    connection.delete_workout(wid)
                else:
                    create_workout = False
                    logging.info("Workout exists and is in sync '%s' on '%s'" % (workout_name,cal_item.get_dt_start()))
            
            if create_workout:
                # Create the workout in the garmin site
                payload = w.create_workout(workout_name)
                logging.info("Creating workout '%s'", workout_name)
                created_workout_json = connection.upload_workout(payload)
                existing_workouts_by_name[workout_name] = created_workout_json
                sync_workouts[Workout.extract_workout_id(created_workout_json)] = cal_item.get_dt_start()

            # Update the workout as found
            existing_workouts_by_name[workout_name]["is_calendar_workout"] = True

        # Delete rest if not found. Only if name starts with T|
        for w in existing_workouts_by_name:
            if "is_calendar_workout" not in existing_workouts_by_name[w]:
                if w[:3] == "T |":
                    # Delete this workout because it is not relevant anymore
                    connection.delete_workout(Workout.extract_workout_id(existing_workouts_by_name[w]))
                    logging.info("Removing workout '%s', because date did not fit time window" % w)

        # Schedule the items on the garmin calendar
        for workout_id in sync_workouts:
            date_workout = sync_workouts[workout_id]
            connection.schedule_workout(workout_id, date_workout)
            logging.info("Workout %s was scheduled on '%s'" % (workout_id, date_workout))

    except Exception as err:
        err.message
        logging.error(err)
        
# def command_list(args):
#     with _garmin_client(args) as connection:
#         for workout in connection.list_workouts():
#             Workout.print_workout_summary(workout)


# def command_get(args):
#     with _garmin_client(args) as connection:
#         workout = connection.get_workout(args.id)
#         Workout.print_workout_json(workout)


# def command_delete(args):
#     with _garmin_client(args) as connection:
#         logging.info("Deleting workout '%s'", args.id)
#         connection.delete_workout(args.id)

# def _garmin_client(args):
#     return GarminClient(username=args.username, password=args.password, cookie_jar=args.cookie_jar)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description="Manage Garmin Connect workout(s)")
    parser.add_argument("--username", "-u", required=True, help="Garmin Connect account username")
    parser.add_argument("--password", "-p", required=True, help="Garmin Connect account password")
    parser.add_argument("--cookie-jar", default=".garmin-cookies.txt", help="Filename with authentication cookies")
    parser.add_argument("--debug", action="store_true", help="Enables more detailed messages")

    subparsers = parser.add_subparsers(title="Commands")

    parser_sync = subparsers.add_parser("sync", description="Sync the workouts")
    # arguments google calendar
    parser_sync.set_defaults(func=command_sync)
    parser_sync.add_argument("--id", required=True, help="Calendar id")
    parser_sync.add_argument("--name", required=True, help="Calendar name")

    # parser_list = subparsers.add_parser("list", description="List all workouts")
    # parser_list.set_defaults(func=command_list)

    # parser_get = subparsers.add_parser("get", description="Get workout")
    # parser_get.add_argument("--id", required=True, help="Workout id, use list command to get workouts identifiers")
    # parser_get.set_defaults(func=command_get)

    parser_dry = subparsers.add_parser("dry", description="Dry run")
    parser_dry.add_argument("--name", required=True, help="The test workout name")
    parser_dry.set_defaults(func=command_dry)

    # parser_delete = subparsers.add_parser("delete", description="Delete workout")
    # parser_delete.add_argument("--id", required=True, help="Workout id, use list command to get workouts identifiers")
    # parser_delete.set_defaults(func=command_delete)

    args = parser.parse_args()

    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=logging_level)

    args.func(args)

if __name__ == "__main__":
    main()