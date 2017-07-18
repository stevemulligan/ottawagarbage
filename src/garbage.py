from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from flask_ask import Ask, statement, dialog, elicit, delegate, question
from configobj import ConfigObj
from geopy.geocoders import GoogleV3
from pyproj import Proj, transform
from datetime import date
import logging
import pprint

config = ConfigObj("../.env")

app = Flask(__name__)

logging.getLogger("flask_ask").setLevel(logging.DEBUG)

app.config['ASK_VERIFY_REQUESTS'] = config['verify_requests']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+mysqldb://%(database_user)s:%(database_password)s@%(database_host)s/%(database_name)s" % config

db = SQLAlchemy(app)
ask = Ask(app, '/')

@ask.intent('AMAZON.StopIntent')
def stop():
    return statement('Ok')

@ask.intent('AMAZON.CancelIntent')
def cancel():
    return statement('Ok')

@ask.intent('AMAZON.HelpIntent')
def help():
    return question('Ottawa Garbage can tell you the next time garbage or recycling will be picked up by asking When is the next pickup date?  Or you can give a specific address like, When is the next pickup date for 190 Main Street?  You can change your address by saying Change my address to 190 Main Street.  You can ask for your current address by asking What is my address.  What would you like to do now?')

@ask.intent('NextPickupForAddress')
def next_pickup_for_address(address):
    connection = db.engine.connect()
    if address != None:
        if ask.request.dialogState == 'COMPLETED':
           new_address = full_address(address)
           location = location_from_address(new_address)
           if (location == None):
               return question("I don't know the address " + address + ". Try a different address near by.")
           else:
               x, y = position_from_location(location)
               return statement("For " + new_address + ", " + pickup_statement_for(x, y))
        else:
           return dialog(delegate())
    return dialog(elicit('address', 'For what address?'))

@ask.intent('ChangeAddress')
def change_address(address):
    connection = db.engine.connect()
    user_id = ask.context.System.user.userId
    if address != None:
        if ask.request.dialogState == 'COMPLETED':
           new_address = set_address_for_user(address, user_id)
           if (new_address == None):
               return question("I don't know the address " + address + ". Try a different address near by.") 
           return statement("Your new address is " + new_address)
        else:
           return dialog(delegate())
    return dialog(elicit('address', 'What is your new address?'))

def set_address_for_user(address, user_id):
    connection = db.engine.connect()
    new_address = full_address(address)
    location = location_from_address(new_address)
    if (location == None):
        return None
    x, y = position_from_location(location)
    latlong = str(location.latitude) + ',' + str(location.longitude)
    connection.execute(text("delete from addresses where user_id=:user_id").bindparams(user_id=user_id))
    connection.execute(text("insert into addresses (user_id, address, latlong, position) values (:user_id, :address, :latlong, POINT(:x, :y))"), user_id=user_id, address=new_address, latlong=latlong, x=x, y=y)
    return new_address

def get_xy_for_user(user_id):
    connection = db.engine.connect()
    result = connection.execute(text("select id, st_x(position) x, st_y(position) y from addresses where user_id = :user_id").bindparams(user_id=user_id)).first()
    return result['x'], result['y']

@ask.intent('CurrentAddress')
def current_address():
    connection = db.engine.connect()
    user_id = ask.context.System.user.userId
    result = connection.execute(text("select address from addresses where user_id = :user_id").bindparams(user_id=user_id)).first()
    if result == None:
       return statement('I have no address on file for you at the moment')
    return statement('Your address is ' + result['address'])

@ask.launch
def start_skill():
    return question('Do you want to know the next pickup date?')

@ask.intent('No')
def no_intent():
    return statement('Have a nice day then eh!')

@ask.intent('NextPickup')
def next_pickup(address):
    connection = db.engine.connect()
    user_id = ask.context.System.user.userId
    if address != None:
        if ask.request.dialogState == 'COMPLETED':
            new_address = set_address_for_user(address, user_id)
            if (new_address == None):
               return question("I don't know the address " + address + ". Try a different address near by.")
            x,y = get_xy_for_user(user_id)
            return statement(pickup_statement_for(x, y))
        else:
            return dialog(delegate())
    result = connection.execute(text("select id, st_x(position) x, st_y(position) y from addresses where user_id = :user_id").bindparams(user_id=user_id))
    if result.rowcount == 0:
        return dialog(elicit('address', 'What is your address'))
    else:
        res = result.first()
        return statement(pickup_statement_for(res['x'], res['y']))

def pickup_statement_for(x, y):
    connection = db.engine.connect()
    weekdays = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
    pickup_res = connection.execute(text("select * from routes where st_contains(area, point(:x, :y))").bindparams(x=x, y=y)).first()
    pickup_day_res = connection.execute(text("SELECT date_add(DATE_ADD(CURDATE(), INTERVAL - WEEKDAY(CURDATE()) DAY), interval :days day) dt").bindparams(days=pickup_res['pickup_day'])).first()
    offset = days_to_offset(pickup_day_res['dt'])
    pickup_day = pickup_res['pickup_day'] + offset
    pickup_with_offset_res = connection.execute(text("select date_add(:date, interval :days day)").bindparams(date=pickup_day_res['dt'], days=offset))
    
    current_weekday_res = connection.execute(text("select weekday(now()) wd")).first()
    current_weekday = current_weekday_res['wd']

    if (pickup_day < current_weekday - 1):
        pickup_str = 'was picked up ' + weekdays[pickup_day] + '.'
    elif (pickup_day == current_weekday - 1):
        pickup_str = 'was picked up yesterday.'
    elif (pickup_day == current_weekday):
        pickup_str = 'was picked up today.'
    elif (pickup_day == current_weekday + 1):
        pickup_str = 'will be picked up tomorrow.'
    else:
        pickup_str = 'will be picked up on ' + weekdays[pickup_day] + '.'

    next_pickup_day_res = connection.execute(text("SELECT date_add(date_add(DATE_ADD(CURDATE(), INTERVAL - WEEKDAY(CURDATE()) DAY), interval 7 day), interval :days day) dt").bindparams(days=pickup_res['pickup_day'])).first()
    next_offset = days_to_offset(next_pickup_day_res['dt'])
    next_pickup_day = pickup_res['pickup_day'] + next_offset

    next_pickup_str = 'is next ' + weekdays[next_pickup_day] + '.'

    week_number_res = connection.execute(text("select weekofyear(now()) wk")).first()
    week_number = week_number_res['wk']

    pickup_type, next_pickup_type = pickup_type_str(pickup_res['schedule'][0], week_number)

    return pickup_type + " " + pickup_str + " " + next_pickup_type + " " + next_pickup_str

def pickup_type_str(schedule, week_number):
    pickup_order = ['Recycling', 'Garbage']
    if (schedule == 'A'):
        pickup_order = list(reversed(pickup_order))

    if (week_number % 2 == 0):
        pickup_order = list(reversed(pickup_order))
 
    return pickup_order[0], pickup_order[1]

def days_to_offset(date):
    connection = db.engine.connect()
    result = connection.execute(text("select count(*) cnt from holidays where year=year(:date) and week_number = weekofyear(:date) and weekday(:date) > weekday").bindparams(date=date)).first()
    return result['cnt']

def full_address(address):
    cities = ["dalmeny","pana","antrim","corkery","dwyer hill","burritts rapids","ashton","galetta","dunrobin","kinburn","kenmore","fallowfield","edwards","sarsfield","vernon","kars","fitzroy harbour","fitzroy","marionville","vars","munster","carp","navan","north gower","cumberland","metcalfe","constance bay","osgoode","richmond","greely","manotick","orleans","barrhaven","stittsville","bells corners","blackburn hamlet","hunt club","morgan's grant","riverside south","riverview","goulbourn","osgoode","rideau","west carleton","rockcliffe park","cumberland","gloucester","kanata","nepean","vanier","gatineau","huntley","torbolton","ottawa"]
    old_address = address.lower()
    if any(old_address.endswith(x) for x in cities):
        new_address = old_address + ", Ontario, Canada"
    else:
        new_address = old_address + ", Ottawa, Ontario, Canada"
    return new_address

def location_from_address(address):
    geolocator = GoogleV3(api_key=config['google_maps_api_key'])
    location = geolocator.geocode(address)
    return location

def position_from_location(location):
    outProj = Proj(init='epsg:2951')
    inProj = Proj(init='epsg:4326')
    x,y = transform(inProj,outProj,location.longitude,location.latitude)
    return x,y
 

if __name__ == '__main__':
    app.run()
