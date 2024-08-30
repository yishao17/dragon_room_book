import flask
from flask import Flask, request
import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import requests
import time
import pytz

secret = "secretkey"
bot = telebot.TeleBot('API_TOKEN', threaded=False)
bot.remove_webhook()
bot.set_webhook(url="https://{pythonanywhere_username}.pythonanywhere.com/{}".format(secret))

ADMIN_USERNAME = "{admin_username}"

def is_admin(user):
    return user == ADMIN_USERNAME

app = Flask(__name__)
@app.route('/{}'.format(secret), methods=["POST"])
def flask_start():
    update = request.get_json()
    if update:
        bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "ok"

# Initialize the database
def setup_db():
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            room TEXT,
            start_date_time TEXT,
            end_date_time TEXT,
            remarks TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# Call this function at the start
setup_db()

def cleanup_expired_bookings():
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    # Get the current date and time
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Delete bookings that are before the current date or, if on the same date, before the current time
    cursor.execute(
        """
        DELETE FROM bookings
        WHERE end_date_time <= ?
        """,
        (today_start,)
    )

    while True:
        cursor.execute(
            """
            SELECT id, user_id, username, room, start_date_time, end_date_time, remarks
            FROM bookings
            ORDER BY username, room, start_date_time
            """
        )
        bookings = cursor.fetchall()

        previous_booking = None
        combined = False  # Flag to track if any combination happened

        for booking in bookings:
            booking_id, user_id, username, room, start_date_time, end_date_time, remarks = booking

            if previous_booking:
                prev_id, prev_user_id, prev_username, prev_room, prev_start_date_time, prev_end_date_time, prev_remarks = previous_booking

                # Check if the current booking can be combined with the previous one
                if (
                    username == prev_username and
                    room == prev_room and
                    remarks == prev_remarks and
                    start_date_time == prev_end_date_time
                ):
                    # Update the end time of the previous booking
                    cursor.execute(
                        """
                        UPDATE bookings
                        SET end_date_time = ?
                        WHERE id = ?
                        """,
                        (end_date_time, prev_id)
                    )

                    # Delete the current booking as it's now merged with the previous one
                    cursor.execute(
                        """
                        DELETE FROM bookings
                        WHERE id = ?
                        """,
                        (booking_id,)
                    )

                    combined = True  # Set the flag to true since a combination occurred
                else:
                    previous_booking = booking
            else:
                previous_booking = booking

        conn.commit()

        # If no combination happened in this iteration, break the loop
        if not combined:
            break

    conn.close()

def format_time(dt):
    time = dt.strftime('%H%M')
    # Combine date and day of the week
    result = f"{time}"
    return result

def format_day(dt):
    # Get day of the week
    day = dt.strftime('%a')
    formatted_date = dt.strftime('%d/%m')
    result = f"{formatted_date} ({day})"
    return result

def format_date_time(dt, time_str):
    hour = int(time_str[:2])
    minute = int(time_str[2:])
    updated_dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return updated_dt

time_list = ['0000','0100', '0200', '0300', '0400', '0500', '0600', '0700', '0800','0900','1000', '1100', '1200', '1300', '1400', '1500', '1600', '1700', '1800','1900','2000','2100','2200','2300']

### START COMMAND ###
@bot.message_handler(commands=['start'])
def welcome(message):
    name_text = f"Hi {message.from_user.first_name}! Welcome to Dragon! This bot is used for room bookings in Dragon.\n"
    intro_text = "\nThe following commands are used in this app:\n"
    select_command = "/select - to book the rooms\n"
    view_all_command = "/view_all - to view all current bookings\n"
    view_own_command = "/view_own - to view your bookings\n"
    cancel_command = "/cancel - to cancel your bookings\n"
    now_command  = "/now - to see which rooms are available now\n"
    help_text = f"{intro_text}{select_command}{view_all_command}{view_own_command}{cancel_command}{now_command} \nor you can use "
    help_command = "/help to view all the commands later!"
    welcome_text = name_text + help_text + help_command
    bot.reply_to(message, text=welcome_text)

### HELP COMMAND ###
@bot.message_handler(commands=['help'])
def help(message):
    intro_text = "Hello! The following commands are used in this app:\n"
    select_command = "/select - to book the rooms\n"
    view_all_command = "/view_all - to view all current bookings\n"
    view_own_command = "/view_own - to view your bookings\n"
    cancel_command = "/cancel - to cancel your bookings\n"
    now_command  = "/now - to see which rooms are available now\n"
    help_text = f"{intro_text}{select_command}{view_all_command}{view_own_command}{cancel_command}{now_command}"
    bot.reply_to(message, text=help_text)

def show_room_selection(chat_id, message_id, optional=0):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton('L6 Lounge', callback_data='selected_rm|L6 Lounge'),
        telebot.types.InlineKeyboardButton('L7 Lounge', callback_data='selected_rm|L7 Lounge'),
    )
    keyboard.row(
        telebot.types.InlineKeyboardButton('L8 Lounge', callback_data='selected_rm|L8 Lounge'),
        telebot.types.InlineKeyboardButton('L6 Study Rm', callback_data='selected_rm|L6 Study Rm'),
    )
    keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
    if optional:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='Please choose a room that you would like to book:', reply_markup=keyboard)
    else:
        ### need to edit this
        bot.reply_to(message=message_id, text='Please choose a room that you would like to book:', reply_markup=keyboard)

### SELECT COMMAND ###
@bot.message_handler(commands=['select'])
def select_handler(message):
    show_room_selection(chat_id=message.chat.id, message_id = message)

### VIEW_ALL COMMAND ###
@bot.message_handler(commands=['view_all'])
def view_all(message):
    cleanup_expired_bookings()
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    cursor.execute("SELECT room, start_date_time, end_date_time, username, remarks FROM bookings ORDER BY room, start_date_time")
    bookings = cursor.fetchall()

    if bookings:
        view_text = "Current bookings:\n"
        current_room = None

        for booking in bookings:
            if booking[0] != current_room:
                view_text += f"\nRoom: {booking[0]}\n"
                current_room = booking[0]
            start_dt = datetime.strptime(booking[1], '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(booking[2], '%Y-%m-%d %H:%M:%S')
            start_date = format_day(start_dt)
            start_time = format_time(start_dt)
            end_time = format_time(end_dt)

            view_text += f"{start_date}: {start_time} - {end_time} by @{booking[3]} for {booking[4]}\n"
    else:
        view_text = "There are no current bookings."

    conn.close()
    bot.reply_to(message, text=view_text)

### VIEW_OWN COMMAND ###
@bot.message_handler(commands=['view_own'])
def view_own(message):
    cleanup_expired_bookings()
    user_id = message.from_user.id
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    cursor.execute("SELECT room, start_date_time, end_date_time, remarks FROM bookings WHERE user_id = ? ORDER BY room, start_date_time", (user_id,))
    bookings = cursor.fetchall()

    if bookings:
        view_text = "Your bookings:\n\n"
        current_room = None

        for booking in bookings:
            if booking[0] != current_room:
                view_text += f"\nRoom: {booking[0]}\n"
                current_room = booking[0]
            start_dt = datetime.strptime(booking[1], '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(booking[2], '%Y-%m-%d %H:%M:%S')
            start_date = format_day(start_dt)
            start_time = format_time(start_dt)
            end_time = format_time(end_dt)

            view_text += f"{start_date}: {start_time} - {end_time} for {booking[3]}\n"
    else:
        view_text = "You have no current bookings."

    conn.close()
    bot.reply_to(message, text=view_text)

### CANCEL COMMAND ###
@bot.message_handler(commands=['cancel'])
def cancel(message):
    user_id = message.from_user.id
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, room, start_date_time, end_date_time FROM bookings WHERE user_id = ? ORDER BY start_date_time", (user_id,))
    bookings = cursor.fetchall()

    if bookings:
        keyboard = telebot.types.InlineKeyboardMarkup()
        for booking in bookings:
            changed_start = booking[2]
            changed_end = booking[3]
            start_dt = datetime.strptime(changed_start, '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(changed_end, '%Y-%m-%d %H:%M:%S')
            start_date = format_day(start_dt)
            start_time = format_time(start_dt)
            end_time = format_time(end_dt)
            keyboard.row(telebot.types.InlineKeyboardButton(f"{booking[1]}: {start_date} {start_time} - {end_time}", callback_data=f"cancel|{booking[0]}"))
        keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
        bot.reply_to(message, text='Select a booking to cancel:', reply_markup=keyboard)
    else:
        bot.reply_to(message, text="You have no bookings to cancel.")

    conn.close()

#CANCEL ADMIN
@bot.message_handler(commands=['cancel_admin'])
def admin(message):
    if is_admin(message.from_user.username):
        conn = sqlite3.connect("room_bookings.db")
        cursor = conn.cursor()

        cursor.execute("SELECT id, room, start_date_time, end_date_time FROM bookings ORDER BY room, start_date_time")
        bookings = cursor.fetchall()

        if bookings:
            keyboard = telebot.types.InlineKeyboardMarkup()
            for booking in bookings:
                changed_start = booking[2]
                changed_end = booking[3]
                start_dt = datetime.strptime(changed_start, '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(changed_end, '%Y-%m-%d %H:%M:%S')
                start_date = format_day(start_dt)
                start_time = format_time(start_dt)
                end_time = format_time(end_dt)
                keyboard.row(telebot.types.InlineKeyboardButton(f"{booking[1]}: {start_date} {start_time} - {end_time}", callback_data=f"cancel|{booking[0]}"))
            keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
            bot.reply_to(message, text='Select a booking to cancel:', reply_markup=keyboard)
        else:
            bot.reply_to(message, text="No bookings to cancel.")

        conn.close()
    else:
        bot.reply_to(message, text="You are not an admin! Please contact @yishao17!")

### CANCEL_ADMIN COMMAND ###
@bot.message_handler(commands=['now'])
def now(message):
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    singapore_tz = pytz.timezone('Asia/Singapore')

    # Get the current time in UTC and convert to Singapore timezone
    utc_now = datetime.now(pytz.utc)
    singapore_time = utc_now.astimezone(singapore_tz)

    # Format the datetime object for SQL query
    current_time_str = singapore_time.strftime('%Y-%m-%d %H:%M:%S')

    # Query to get all rooms that are currently booked
    cursor.execute(
        """
        SELECT DISTINCT room
        FROM bookings
        WHERE start_date_time <= ? AND end_date_time > ?
        """,
        (current_time_str, current_time_str)
    )
    booked_rooms = {row[0] for row in cursor.fetchall()}

    # Assume a predefined list of all possible rooms
    custom_order = ['L6 Lounge', 'L7 Lounge', 'L8 Lounge', 'L6 Study Rm']  # Specify desired order

    # Find rooms that are not booked
    available_rooms = [room for room in custom_order if room not in booked_rooms]

    conn.close()
    keyboard = telebot.types.InlineKeyboardMarkup()

    if available_rooms:
        available_rooms_str = '\n'.join(f"- {room}" for room in available_rooms)
        text_to_reply = f"The following rooms are available now:\n\n{available_rooms_str}\n\nPlease book them if you want to use them!"
        # Add buttons for each available room
        for room in available_rooms:
            keyboard.row(
                telebot.types.InlineKeyboardButton(f'{room}', callback_data=f'selected_rm|{room}'),
            )
        keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
    else:
        text_to_reply = "Currently, no rooms are available. Please check back later!"
        keyboard = None

    # Send the message with the inline keyboard
    bot.reply_to(message, text=text_to_reply, reply_markup=keyboard)

### CANCEL SELECTION HANDLER ###
@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel|'))
def confirm_cancel(call):
    booking_id = call.data.split('|')[1]
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()

    cursor.execute("SELECT room, start_date_time, end_date_time FROM bookings WHERE id = ?", (booking_id,))
    booking = cursor.fetchone()

    if booking:
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "Booking cancelled!")
        changed_start = datetime.strptime(booking[1], '%Y-%m-%d %H:%M:%S')
        changed_end = datetime.strptime(booking[2], '%Y-%m-%d %H:%M:%S')
        start_date = format_day(changed_start)
        start_time = format_time(changed_start)
        end_time = format_time(changed_end)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Cancelled booking for {booking[0]}: {start_date} {start_time} - {end_time}")
    else:
        bot.answer_callback_query(call.id, "Booking not found!")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Booking not found.")

    conn.close()

### ROOM SELECTION HANDLER ###
@bot.callback_query_handler(func=lambda call: call.data.startswith('selected_rm|'))
def select_date(call):
    room = call.data.split('|')[1]
    bot.answer_callback_query(call.id)

    today = datetime.today()
    dates = [today + timedelta(days=i) for i in range(8)]
    keyboard = telebot.types.InlineKeyboardMarkup()

    for i in range(0, len(dates), 2):
        start_date1 = dates[i].replace(hour=0, minute=0, second=0, microsecond=0)
        start_date2 = dates[i+1].replace(hour=0, minute=0, second=0, microsecond=0)
        final_start_date1 = start_date1.strftime('%Y%m%d%H%M')
        final_start_date2 = start_date2.strftime('%Y%m%d%H%M')
        display_str1 = format_day(dates[i])
        display_str2 = format_day(dates[i+1])
        keyboard.row(
            telebot.types.InlineKeyboardButton(display_str1, callback_data=f"rm_start|{room}|{final_start_date1}"),
            telebot.types.InlineKeyboardButton(display_str2, callback_data=f"rm_start|{room}|{final_start_date2}")
            )
    keyboard.row(telebot.types.InlineKeyboardButton("Change Room", callback_data="change_rm|"))
    keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
    try:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f'{room} \n\nStart date:', reply_markup=keyboard)
    except Exception as e:
        print(f"{datetime.now().strftime('%H%M')}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rm_start|'))
def select_time(call):
    inital, room, start_date_str = call.data.split('|')
    bot.answer_callback_query(call.id)

    keyboard = telebot.types.InlineKeyboardMarkup()

    for i in range(0, len(time_list), 6):
        keyboard.row(
            telebot.types.InlineKeyboardButton(time_list[i], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 1], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i + 1]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 2], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i + 2]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 3], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i + 3]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 4], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i + 4]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 5], callback_data=f"selected_starttime|{room}|{start_date_str}|{time_list[i + 5]}")
        )
    keyboard.row(telebot.types.InlineKeyboardButton("Change Date", callback_data=f"change_SD|{room}"))
    keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
    try:
        dt = datetime.strptime(start_date_str, '%Y%m%d%H%M')
        nice_dt = dt.strftime('%d/%m (%a)')
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f'{room} \nDate: {nice_dt} \n\nStart time:', reply_markup=keyboard)
    except Exception as e:
        print(f"{datetime.now().strftime('%H%M')}: {e}")

### TIME SELECTION HANDLER ###
@bot.callback_query_handler(func=lambda call: call.data.startswith('selected_starttime|'))
def select_end_time(call):
    inital, room, start_date_str, start_time = call.data.split('|')
    start_dt = format_date_time(datetime.strptime(start_date_str, '%Y%m%d%H%M'), start_time)
    final_start = start_dt.strftime('%Y%m%d%H%M')
    bot.answer_callback_query(call.id)

    keyboard = telebot.types.InlineKeyboardMarkup()

    for i in range(0, len(time_list), 6):
        keyboard.row(
            telebot.types.InlineKeyboardButton(time_list[i], callback_data=f"endtime|{room}|{final_start}|{time_list[i]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 1], callback_data=f"endtime|{room}|{final_start}|{time_list[i + 1]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 2], callback_data=f"endtime|{room}|{final_start}|{time_list[i + 2]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 3], callback_data=f"endtime|{room}|{final_start}|{time_list[i + 3]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 4], callback_data=f"endtime|{room}|{final_start}|{time_list[i + 4]}"),
            telebot.types.InlineKeyboardButton(time_list[i + 5], callback_data=f"endtime|{room}|{final_start}|{time_list[i + 5]}")
        )
    keyboard.row(telebot.types.InlineKeyboardButton("Change Start Time", callback_data=f"change_ST|{room}|{start_date_str}"))
    keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
    try:
        dt1 = datetime.strptime(final_start, '%Y%m%d%H%M')
        nice_dt1 = dt1.strftime('%d/%m (%a) %H%M')
        timing_only = dt1.strftime('%H%M')
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f'{room} \nDate: {nice_dt1} \n\nEnd time (after {timing_only}):', reply_markup=keyboard)
    except Exception as e:
        print(f"{datetime.now().strftime('%H%M')}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('endtime|'))
def confirm_booking(call):
    initial, room, start_date_str, end_time = call.data.split('|')
    copy_start_date_str = datetime.strptime(start_date_str, '%Y%m%d%H%M')
    ## see if can dn to make a copy^^^
    start_dt = datetime.strptime(start_date_str, '%Y%m%d%H%M')
    if end_time == '0000':
        end_dt = copy_start_date_str.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        end_dt = datetime.strptime(start_date_str[:8] + end_time, '%Y%m%d%H%M')
    nice_end = end_dt.strftime('%H%M')
    final_end = end_dt.strftime('%Y%m%d%H%M')
    nice_start = start_dt.strftime('%d/%m (%a) %H%M')
    bot.answer_callback_query(call.id)
    if start_date_str >= final_end:
        ###################
        #include try again#
        ###################
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Invalid Response, end time cannot be same as/earlier than start time \nPlease try again!")
        show_room_selection(chat_id=call.message.chat.id, message_id=call.message)
    else:
        conn = sqlite3.connect("room_bookings.db")
        cursor = conn.cursor()
        # Check if the room is already booked at that date and time
        cursor.execute(
            """
            SELECT * FROM bookings
            WHERE room = ?
            AND (
                (start_date_time <= ? AND end_date_time > ?) OR
                (start_date_time < ? AND end_date_time >= ?) OR
                (start_date_time >= ? AND end_date_time <= ?)
            )
            """,
            (room, start_dt, start_dt, end_dt, end_dt, start_dt, end_dt)
        )
        booking = cursor.fetchone()

        if booking:
            username = booking[2]
            dt1 = datetime.strptime(booking[4], '%Y-%m-%d %H:%M:%S')
            nice_dt1 = dt1.strftime('%d/%m (%a) %H%M')
            dt2 = datetime.strptime(booking[5], '%Y-%m-%d %H:%M:%S')
            nice_dt2 = dt2.strftime('%H%M')
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Sorry, {room} is already booked by @{username} from {nice_dt1} - {nice_dt2}! \nPlease try again!")
            show_room_selection(chat_id=call.message.chat.id, message_id=call.message)
        else:
            remark = ['Grp Meeting', 'HC Event', 'Interview', 'Other Reasons']
            keyboard = telebot.types.InlineKeyboardMarkup()
            for i in range(0, len(remark), 2):
                keyboard.row(
                    telebot.types.InlineKeyboardButton(remark[i], callback_data=f"final|{room}|{start_date_str}|{final_end}|{remark[i]}"),
                    telebot.types.InlineKeyboardButton(remark[i+1], callback_data=f"final|{room}|{start_date_str}|{final_end}|{remark[i+1]}")
                    )
            keyboard.row(telebot.types.InlineKeyboardButton("Change End Time", callback_data=f"change_ET|{room}|{start_date_str}|{start_date_str[-4:]}"))
            keyboard.row(telebot.types.InlineKeyboardButton("Cancel", callback_data=f"change_cancel|"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"{room} \n{nice_start} - {nice_end} \n\nReason for booking:", reply_markup=keyboard)
        cursor.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('final'))
def insert_into_table(call):
    initial, room, start_date_str, end_date_str, remark = call.data.split('|')
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()
    user_id = call.from_user.id
    username = call.from_user.username
    final_start = datetime.strptime(start_date_str, '%Y%m%d%H%M')
    final_end = datetime.strptime(end_date_str, '%Y%m%d%H%M')
    nice_start = final_start.strftime('%d/%m (%a) %H%M')
    nice_end = final_end.strftime('%H%M')
    cursor.execute(
        "INSERT INTO bookings (user_id, username, room, start_date_time, end_date_time, remarks) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, room, final_start, final_end, remark)
    )
    conn.commit()
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"@{username} booked {room} from {nice_start} - {nice_end} for {remark}!")

    conn.close()


def reset_db():
    conn = sqlite3.connect("room_bookings.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS bookings")
    cursor.execute(
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            room TEXT,
            start_date_time TEXT,
            end_date_time TEXT,
            remarks TEXT
        )
        """
    )
    conn.commit()
    conn.close()

@bot.message_handler(commands=['reset'])
def reset(message):
    if is_admin(message.from_user.username):
        reset_db()
        bot.reply_to(message, text="reset!")
    else:
        bot.reply_to(message, text="You are not an admin! Please contact @yishao17!")

### ALL OTHER MESSAGES HANDLING ###
@bot.message_handler(func=lambda message: True)
def reply_func(message):
    bot.reply_to(message, text="Please only select the commands given!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('change_'))
def back(call):
    initial = call.data.split('|')[0]
    if initial == 'change_rm':
        show_room_selection(chat_id=call.message.chat.id, message_id=call.message.message_id, optional=1)
    elif initial == 'change_SD':
        select_date(call)
    elif initial == 'change_ST':
        select_time(call)
    elif initial == 'change_ET':
        select_end_time(call)
    elif initial == 'change_cancel':
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
