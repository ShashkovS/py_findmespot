import os
import sqlite3

import datetime

sqlite_db_path = r'db/tracks2.db'
DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
NOW_TIME = datetime.datetime.now().astimezone(datetime.timezone.utc).strftime(DB_TIME_FORMAT)


def UTC_ts_to_fms_ts(dt):
    return dt.astimezone(datetime.timezone(offset=datetime.timedelta(hours=-8))).strftime("%Y-%m-%dT%H:%M:%S%z")


def fms_ts_to_UTC_ts(ts_utc):
    dt = datetime.datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%S%z")
    return dt.astimezone(datetime.timezone.utc)


def set_db_path(db_path):
    global sqlite_db_path
    sqlite_db_path = db_path


def check_base():
    if not os.path.isfile(sqlite_db_path):
        _create_base()


def _create_base():
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS findmespot_keys (
                         fms_key_id INTEGER PRIMARY KEY, 
                         fms_key text, 
                         last_rqs_ts timestamp, 
                         last_waypoint_ts timestamp
                     )""")
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS findmespot_keys_by_fms_key on findmespot_keys (fms_key)""")
        c.execute("""CREATE TABLE IF NOT EXISTS trips (
                         name text PRIMARY KEY, 
                         date_s timestamp,
                         date_e timestamp,
                         fms_key_id int, 
                         FOREIGN KEY(fms_key_id) REFERENCES findmespot_keys(fms_key_id)
                     )""")
        c.execute("""CREATE TABLE IF NOT EXISTS waypoints (
                         waypoint_id INTEGER PRIMARY KEY, 
                         fms_key_id int, 
                         id_from_fms text, 
                         lat float, 
                         long float, 
                         alt float, 
                         ts timestamp, 
                         batteryState text, 
                         msg text,
                         FOREIGN KEY(fms_key_id) REFERENCES findmespot_keys(fms_key_id)
                     )""")
        c.execute("""CREATE INDEX IF NOT EXISTS waypoints_by_fms_key_id on waypoints (fms_key_id)""")
        conn.commit()


def get_trip_attributes(id):
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        c.execute("""SELECT fms_key, last_waypoint_ts, last_rqs_ts FROM findmespot_keys WHERE fms_key_id = ?""", (id,))
        return c.fetchall()


def all_current_trips():
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        c.execute("""SELECT fms_key_id FROM trips WHERE date_e >= ?""", (NOW_TIME,))
        return c.fetchall()


def checking_last_time(fms_key_id, ts):
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        time = \
        c.execute("SELECT last_waypoint_ts FROM findmespot_keys where fms_key_id = ?", (fms_key_id,)).fetchall()[0][0]
        time = datetime.datetime.strptime(time, DB_TIME_FORMAT).astimezone(datetime.timezone.utc)
        return time < ts


def update_tables(messages: dict, key: str):
    alt = messages['altitude']
    lat = messages['latitude']
    long = messages['longitude']
    ts = messages['dateTime']
    ts = fms_ts_to_UTC_ts(ts)
    battery_state = messages['batteryState']
    msg = messages.get('messageContent', '')
    with sqlite3.connect(sqlite_db_path) as conn:
        try:
            c = conn.cursor()
            fms_key_id = c.execute("SELECT fms_key_id FROM findmespot_keys where fms_key = ?", (key,)).fetchall()[0][0]
            id_from_fms = messages['id']
            c.execute(f"""INSERT into waypoints (fms_key_id, id_from_fms, lat, long, alt, ts, batteryState, msg)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (fms_key_id, id_from_fms, lat, long, alt, ts, battery_state, msg))
            if checking_last_time(fms_key_id, ts):
                c.execute("UPDATE findmespot_keys SET last_waypoint_ts = ? where fms_key_id = ?",
                          (ts.strftime(DB_TIME_FORMAT), fms_key_id))
            c.execute("UPDATE findmespot_keys SET last_rqs_ts = ? where fms_key_id = ?", (NOW_TIME, fms_key_id))
            conn.commit()
        except:
            conn.rollback()


def get_waypoints_by_trip(trip_name: str):
    with sqlite3.connect(sqlite_db_path) as con:
        cur = con.cursor()
        table = cur.execute('''SELECT * FROM trips where name = ?''', (trip_name,))
        name, date_s, date_e, fms_id = table.fetchall()[0]
        waypoints = cur.execute('''SELECT * FROM waypoints where fms_key_id = ?''', (str(fms_id),)).fetchall()
    return waypoints


def create_new_trip(trip_name: str, fms_trip_id: str, date_start: datetime.datetime, date_end: datetime.datetime):
    with sqlite3.connect(sqlite_db_path) as con:
        cur = con.cursor()

        cur.execute('''INSERT  INTO findmespot_keys (fms_key, last_rqs_ts, last_waypoint_ts) VALUES (?, ?, ?)''',
                    (str(fms_trip_id), date_start.strftime(DB_TIME_FORMAT),
                     date_end.strftime(DB_TIME_FORMAT)))
        db_id = \
            cur.execute('''SELECT fms_key_id from findmespot_keys where fms_key = ?''', (str(fms_trip_id),)).fetchall()[
                0][
                0]
        cur.execute('''INSERT INTO trips VALUES (?, ?, ?, ?)''', (str(trip_name), date_start.strftime(DB_TIME_FORMAT),
                                                                  date_end.strftime(DB_TIME_FORMAT), int(db_id)))
        con.commit()
