from flask import Flask, jsonify, request;
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from bson import json_util
import json
import os
import razorpay
import certifi
import googlemaps
import jwt
from functools import wraps
import datetime

ca = certifi.where()


gmaps = googlemaps.Client(key='AIzaSyAL9K2tfUIeuX0SkO2EZ4Ig55gbtPeZs-c')




load_dotenv()

app = Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY') or 'bamsi'
print(SECRET_KEY)
app.config['SECRET_KEY'] = SECRET_KEY





client = MongoClient("mongodb+srv://bamsi:Alcuduur40@cluster0.vtlehsn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", tlsCAFile=ca)

db = client["vihari"]
CORS(app, resources={r"/*": {"origins": "*"}})


def getCurrentUser(id):
    admin = db["Admins"].find_one({"_id": ObjectId(id)})
    zoneAdmin = db['ZoneAdmins'].find_one({"_id": ObjectId(id)})
    driver = db['Driver'].find_one({"_id": ObjectId(id)})

    return zoneAdmin['_id'] if admin is None else admin['_id']

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]
        if not token:
            return {
                "message": "Authentication Token is missing!",
                "data": None,
                "error": "Unauthorized"
            }, 401
        try:
            data=jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user= getCurrentUser(data["user_id"])
            if current_user is None:
                return {
                "message": "Invalid Authentication token!",
                "data": None,
                "error": "Unauthorized"
            }, 401
            
        except Exception as e:
            return {
                "message": "Something went wrong",
                "data": None,
                "error": str(e)
            }, 500

        return f(current_user, *args, **kwargs)

    return decorated




@app.route('/')
def start():
    # print(currentUser)
    return "Vihari api is working....."


@app.route('/order', methods=["POST"])
def order():
    incoming_msg = request.get_json();

    razor = razorpay.Client(auth=("rzp_live_nma9bpaQRoARQg", "re38c3NxNAoGlfKs4aDPJPq8"))

    options = {
        'amount': incoming_msg['amount'] * 100,
        'currency': 'INR',
        'receipt': incoming_msg['firstname'] + "937932",
        'payment_capture': 1
    }

    response = razor.order.create(data=options)

    return response


@app.route('/createZone', methods=["POST"])
@token_required
def zone(currentUser):
    incoming_msg = request.get_json();
    zone = db['Zone']
    admin = db["Admins"]
    zone_check = zone.find_one({"zone_name": incoming_msg["zoneName"].upper()})
    
    if zone_check:
        return "already zone created", 404
    else:
        zone_dict = {
            "zone_name": incoming_msg['zoneName'].upper(),
            "added_by": admin.find_one({"_id": ObjectId(currentUser)})["role"],
            "geofence_radius": incoming_msg['geofence'],
            "price_matrix": [],
            "total_vehicles": [],
            'hourly_price': [],
            'hourly_price_round':[],
            "total_drivers": "",
            "status": "active"
        }

        zone.insert_one(zone_dict)
        return "working....", 200
    # print(driver)
    # print(driver.find())
    
    

@app.route('/setPriceZone', methods=["POST"])
@token_required
def pricing(currentUser):
    incoming_msg = request.get_json();
    zone = db['Zone'];
    vehicleType = incoming_msg['zoneName']['vehicleType'] if incoming_msg['trip'] == 'oneWay' else incoming_msg['vehicleType']
    # print(vehicleType)
    if incoming_msg['trip'] == "oneWay":
        up = zone.update_one({
            'zone_name': incoming_msg['zoneName']['zoneName']
        }, {
            "$set": {
                vehicleType : {
                    "price_per_km": incoming_msg['zoneName']['pricePerKm'], 
                    "hourly_price": incoming_msg['zoneName']['hourlyPrice']
                    
                }
                
            }
        })
    else:
        up = zone.update_one({
            'zone_name': incoming_msg['zoneName']['zoneName']
        }, {
            "$set": {
                vehicleType + "_round": {
                    "price_perkm_round": incoming_msg['priceroundTrip'],
                    "hourly_price_round": incoming_msg['hourlyPrice']
                }
            }
            
        })
    print(up)
    return "worked,,,"



@app.route('/setBooking', methods=["POST"])
def setBooking():
        incoming_msg = request.get_json()['Body'];
        customer = db['Customer'].find_one({"firstname": incoming_msg['firstname']})
        bookings = db['Bookings']
        vehicles = db['Vehicles']
        zone = db["Zone"].find_one({'zone_name': incoming_msg['from'].upper()})
        # print(incoming_msg['car_model'])
        capacity = vehicles.find_one({"vehicle_type": incoming_msg['car_model'], "zone_id": zone['_id']})
        
        print(capacity)
        carZone = db['Zone'].find_one({"_id": capacity['zone_id']})
        # print(capacity)
        
        payload = {
            "orginZone": incoming_msg['from'],
            "to": incoming_msg['to'],
            "duration": incoming_msg['duration'],
            "distance": incoming_msg['distance'],
            "paymentId": incoming_msg['paymentId'] if incoming_msg['payment_type'] != "COD" else "",
            "total_trip_price": incoming_msg['price'],
            "trip_type": incoming_msg['tripType'],
            'trip_start_datetime': incoming_msg['time'],
            'trip_end_datetime': incoming_msg['trip_end_datetime'] if incoming_msg['tripType'] == "roundTrip" else "",
            'car_capacity': capacity['capacity'],
            'travel_date': incoming_msg['travel_date'],
            'car_type': incoming_msg['car_model'],
            'car_zone': carZone['zone_name'],
            'car_info': '',
            'booking_price': '',
            'payment_status': 'Paid' if incoming_msg['payment_type'] != "COD" else "PENDING",
            'payment_type': incoming_msg['payment_type'],
            'user_id': customer['_id'],
            'extra_payment_details': '',
            'status': 'Booked'

        }
        
        user = db["Customer"].update_one({
            "email": incoming_msg['email'],
        } , {
            '$push': {
                "booking_history": payload
            }
        }
        
        )
        bookings.insert_one(payload)
        j = list(bookings.find())[-1]
        # print(j['_id'])
        return {
            "bookingId":str(j['_id'])
        }


@app.route('/getBookings')
@token_required
def getBookings(current):
    bookins = db['Bookings']
    all = list(bookins.find())
    return json.loads(json_util.dumps(all))


@app.route('/getZones')
@token_required
def getzones(currentUser):
    zones = db['Zone']
    
    zone = zones.find()
    zone_list = list(zone)
    # for items in zone:
    #     zone_dict = {
    #         "zone_name": items["zone_name"],
    #         "geofence_radius": items["geofence_radius"],
    #         "price_matrix": items["price_matrix"],
    #         "total_vehicles": items["total_vehicles"],
    #         "total_drivers": items["total_drivers"]
    #     }
    # zone_list.append(zone_dict)
    
    
    return json.loads(json_util.dumps(zone_list))


@app.route('/getVendors')
@token_required
def getvendors(current):
    vendors = db['Vendors']
    
    vendor = vendors.find()
    vendor_list = list(vendor)
    # for items in zone:
    #     zone_dict = {
    #         "zone_name": items["zone_name"],
    #         "geofence_radius": items["geofence_radius"],
    #         "price_matrix": items["price_matrix"],
    #         "total_vehicles": items["total_vehicles"],
    #         "total_drivers": items["total_drivers"]
    #     }
    # zone_list.append(zone_dict)
    
    
    return json.loads(json_util.dumps(vendor_list))


@app.route('/getVehicles')
@token_required
def getVehicles(current):
    vehicles = db['Vehicles']
    
    vehicle = vehicles.find()
    vehicles_list = list(vehicle)
    
    return json.loads(json_util.dumps(vehicles_list))

@app.route('/getUsers')
@token_required
def getUsers(current):
    users = db['Customer']
    
    user = users.find()
    users_list = list(user)
    
    return json.loads(json_util.dumps(users_list))

@app.route('/getUser', methods=["POST"])
@token_required
def getUser(current):
    incoming_msg = request.get_json()
    users = db['Customer']
    
    user = users.find_one({"_id":ObjectId(incoming_msg['userId'])})
    users_list = list(user)
    
    return json.loads(json_util.dumps(users_list))

@app.route('/getZoneAdmins')
@token_required
def getZoneAdmins(current):
    zoneAdmins = db['ZoneAdmins']
    
    zoneAdmin = zoneAdmins.find()
    zoneadmin_list = list(zoneAdmin)
    
    return json.loads(json_util.dumps(zoneadmin_list))

@app.route('/trips')
@token_required
def trips(current):
    bookings = db['Bookings']
    vehicles = db["Vehicles"]
    zone = db["Zone"]
    driver = db['Driver']
    # print(list(driver))
    all = list(bookings.find())
    f = []
    
    # print(vehicle)
    for i in all:
        zones = i['orginZone']
        vehicle_type = i['car_type']
        
        f.append(
            {
               "orderId": i["_id"],
               "originZone": i['orginZone'],
               "destination": i['to'],
               "tripType": i['trip_type'],
               "payment_status": i['payment_status'],
               "vehicle": list(vehicles.find({"vehicle_type": vehicle_type, "status": "active", "zone_id": zone.find_one({"zone_name": zones.upper()})['_id']})),
               "Driver":list(driver.find({"status": "", "zone.zone_name": zones.upper()})),
               "status": i['status'],
               "car_type": i['car_type'],
               "travel_date": i['travel_date']
            }
        )
    # print(f)
    return json.loads(json_util.dumps(f))
    

@app.route('/getDrivers')
@token_required
def getDrivers(current):
    drivers = db['Driver']
    
    driver = drivers.find()
    driver_list = list(driver)
    # for items in zone:
    #     zone_dict = {
    #         "zone_name": items["zone_name"],
    #         "geofence_radius": items["geofence_radius"],
    #         "price_matrix": items["price_matrix"],
    #         "total_vehicles": items["total_vehicles"],
    #         "total_drivers": items["total_drivers"]
    #     }
    # zone_list.append(zone_dict)
    
    
    return json.loads(json_util.dumps(driver_list))


@app.route('/startTrip', methods=["POST"])
@token_required
def startTrip(current):
    incoming_msg = request.get_json()
    driver = db['Driver']

    vehicle = db['Vehicles']
    cartype = db['Bookings'].find_one({"_id": ObjectId(incoming_msg['bookingId'])})
    print(incoming_msg['bookingId'])
    vehicle.update_one({
        "vehicle_type": cartype['car_type'], "vehicle_name": incoming_msg['vehicleName'], "brand": incoming_msg['brand']
    }, {
        '$set': {
            "status":"assigned"
        }
    })
    payload = {
        "bookingId": ObjectId(incoming_msg["bookingId"]),
        "travel_Date": incoming_msg['travelDate'],
        "trip_status": ""
    }
    driver.update_one({
        "firstname": incoming_msg['driverFirstName'], "lastname": incoming_msg['driverLastName']
    }, {"$set": {
        "status": "assigned",
    }, 
        "$push": {
            "trips": payload,
        }
    })
    db['Bookings'].update_one({
        "_id": ObjectId(incoming_msg['bookingId'])
    }, {
        "$set": {
            "status": "trip confirmed"
        }

    })

    return "Booked....."




@app.route('/createDriver', methods=["POST"])
@token_required
def createDriver(currentUser):
    incoming_msg = request.get_json()["Body"];
    drivers = db["Driver"]
    zone = db["Zone"]
    zone = db["Zone"].find_one({"zone_name": incoming_msg["zone"]})
    driver_check = drivers.find_one({"mobile": incoming_msg['mobile']})
    customer_check = db['Customer'].find_one({"mobile": incoming_msg['mobile']})
    vendor_check = db['Vendors'].find_one({"mobile": incoming_msg['mobile']})
    if "Authorization" in request.headers:
        token = request.headers["Authorization"].split(" ")[1]
        print(token)
    if driver_check or customer_check or vendor_check:
        return "this number already used", 404
    
    else:
        driver_dict = {
            "firstname": incoming_msg["firstName"],
            "lastname": incoming_msg["lastName"],
            "mobile": incoming_msg["mobile"],
            "alt_mobile": incoming_msg["altNumber"],
            "email": incoming_msg["email"],
            "zone": zone,
            "license_number":incoming_msg["licenseNumber"],
            "driving_license":incoming_msg["drivingPhoto"],
            "id_proof_front_url": incoming_msg["imgUrl"],
            "address_proof_url": incoming_msg["addressProof"],
            "pan_card": incoming_msg["pan"],
            "status": "",
            "trips": []

        }
        drivers.insert_one(driver_dict)

        return "working..."

@app.route('/createAdmin')
def createAdmin():
    # incoming_msg = request.get_json();
    
    admin = db['Admins']
    zones = db["Zone"]
    zoneAdmin = zones.find_one({"zone_admin.name": "Bamsi"})
    admin_dict = {
        "firstname": "Mr",
        "lastName": "Ramarao",
        "contact": "+919493555253",
        "email": "",
        "license_number": "",
        "role": 'admin'
    }
    admin.insert_one(admin_dict)
    # print(zoneAdmin)
    return "working..."


@app.route('/createCustomer', methods=["POST"])
def createCustomer():
    incoming_msg = request.get_json()
    customer = db['Customer']
    drivers = db['Driver']
    email = customer.find_one({"email": incoming_msg['email']})
    driver_check = drivers.find_one({"mobile": incoming_msg['phoneNumber']})
    customer_check = db['Customer'].find_one({"mobile": incoming_msg['phoneNumber']})
    vendor_check = db['Vendors'].find_one({"mobile": incoming_msg['phoneNumber']})
    if driver_check or customer_check or vendor_check or email:
        return "this number already used or email", 404

    else:
        customer_dict = {
            "firstname": incoming_msg['firstName'],
            "lastname": incoming_msg['lastName'],
            "mobile": incoming_msg["phoneNumber"],
            "email": incoming_msg['email'],
            "location": {
                "lat": '',
                "long": ''
            },
            "search_history": [],
            "booking_history": [],
            "total_payments": "",
            "pending_payments": "",
            "feedback": [],
            "status": "",
            "profile_url": "",
            'role': "user"
        }

        customer.insert_one(customer_dict)
        
    # print(incoming_msg)
    return "working...."

@app.route('/checkCustomer', methods=["POST"])
def checkCustomer():
    incoming_msg = request.get_json()
    customers = db['Customer']
    admin = db['Admins']
    zoneAdmin = db['ZoneAdmins']
    vendor = db['Vendors']
    onlyDriver = db['Driver'].find_one({"mobile": incoming_msg["phoneNumber"]})
    customer = customers.find_one({"mobile": incoming_msg["phoneNumber"]})
    onlyAdmin = admin.find_one({"contact": incoming_msg['phoneNumber']})
    onlyZoneAdmin = zoneAdmin.find_one({"mobile": incoming_msg['phoneNumber']})
    onlyVendors = vendor.find_one({"mobile": incoming_msg['phoneNumber']})


    if customer:
        return json.loads(json_util.dumps(customer))
    elif onlyAdmin:
        tokenAdmin = jwt.encode({'user_id' : str(onlyAdmin['_id']), 'exp' : datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'], "HS256")
        admin.update_one(onlyAdmin, {
            "$set": {
                "token": tokenAdmin
            }
        })
        # print(onlyAdmin['_id'])
        return {
            "admin": json.loads(json_util.dumps(onlyAdmin)),
            "token":tokenAdmin
        } 
    elif onlyZoneAdmin:
        tokenzoneAdmin = jwt.encode({'user_id' : str(onlyZoneAdmin['_id']), 'exp' : datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'], "HS256")
        zoneAdmin.update_one(onlyZoneAdmin, {
            "$set": {
                "token": tokenzoneAdmin
            }
        })
        return {
            "zoneAdmin": json.loads(json_util.dumps(onlyZoneAdmin)),
            "token": tokenzoneAdmin
        }
    elif onlyVendors:
        return json.loads(json_util.dumps(onlyVendors))
    elif onlyDriver:
        token = jwt.encode({'user_id' : str(onlyDriver['_id']), 'exp' : datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'], "HS256")
        db['Driver'].update_one(onlyDriver, {
            "$set": {
                "token": token
                # "token": jwt({"user_id": str(onlyDriver["_id"])}, "driver", )
            }
        })
        return {
            "driver": json.loads(json_util.dumps(onlyDriver)),
            "token": token
        }
    else:
        return "You are not registered, please register first", 400





@app.route('/createVendor', methods=["POST"])
@token_required
def createVendor(current):
    incoming_msg = request.get_json()["Body"];
    vendors = db['Vendors']
    zone = db["Zone"].find_one({"zone_name": incoming_msg["zone"]})
    drivers = db['Driver']
    driver_check = drivers.find_one({"mobile": incoming_msg['mobile']})
    customer_check = db['Customer'].find_one({"mobile": incoming_msg['mobile']})
    vendor_check = db['Vendors'].find_one({"mobile": incoming_msg['mobile']})
    if driver_check or customer_check or vendor_check:
        return "this number already used", 404

    else:
        vendors_dict = {
            "zone_id": zone['_id'],
            "firstname": incoming_msg["firstName"],
            "lastname": incoming_msg["lastName"],
            "mobile": incoming_msg["mobile"],
            "alt_mobile": incoming_msg["altNumber"],
            "email": incoming_msg["email"],
            "license_number": incoming_msg["licenseNumber"],
            "driving_license_front_url": incoming_msg["drivingPhoto"],
            "driving_license_back_url": "",
            "address_proof_url": incoming_msg["imgUrl"],
            "id_proof_front_url" :"",
            "id_proof_back_url": "",
            "profile_url": incoming_msg["profilePic"],
            "pan_card": "",
            "role": "vendor"
            
        }

        vendors.insert_one(vendors_dict)
        # print(incoming_msg)
        return "working....."

@app.route('/createZoneAdmin', methods=["POST"])
@token_required
def createZoneAdmin(current):
    incoming_msg = request.get_json()["Body"];
    zone_admins = db['ZoneAdmins']
    zone = db["Zone"].find_one({"zone_name": incoming_msg["zone"]})
    drivers = db['Driver']
    driver_check = drivers.find_one({"mobile": incoming_msg['mobile']})
    customer_check = db['Customer'].find_one({"mobile": incoming_msg['mobile']})
    vendor_check = db['Vendors'].find_one({"mobile": incoming_msg['mobile']})
    if driver_check or customer_check or vendor_check:
        return "this number already used", 404
    
    else:
        vendors_dict = {
            "zone_id": zone['_id'],
            "firstname": incoming_msg["firstName"],
            "lastname": incoming_msg["lastName"],
            "mobile": incoming_msg["mobile"],
            "alt_mobile": incoming_msg["altNumber"],
            "email": incoming_msg["email"],
            "license_number": incoming_msg["licenseNumber"],
            "driving_license_front_url": incoming_msg["drivingPhoto"],
            "driving_license_back_url": "",
            "address_proof_url": incoming_msg["imgUrl"],
            "id_proof_front_url" :"",
            "id_proof_back_url": "",
            "profile_url": incoming_msg["profilePic"],
            "pan_card": "",
            "role": "zoneAdmin"
            
        }

        zone_admins.insert_one(vendors_dict)
        # print(incoming_msg)
        return "working....."

@app.route('/createVehicle', methods=["POST"])
@token_required
def createVehicle(current):
    incoming_msg = request.get_json()["Body"];
    vehicles = db['Vehicles']
    zone = db["Zone"].find_one({"zone_name": incoming_msg["zone"]})
    checkRegisterNumber = vehicles.find_one({"registration_number": incoming_msg["registerNumber"]})
    vehicle_dict = {
        "zone_id": zone['_id'],
        "vehicle_name": incoming_msg["vehicleName"],
        "vehicle_type": incoming_msg["vehicleType"],
        "brand": incoming_msg["brand"],
        "capacity": incoming_msg["capacity"],
        "mileage": incoming_msg["mileage"],
        'zone': zone,
        "vehicle_owner": incoming_msg["ownerType"],
        "added_by" :incoming_msg["addedBy"],
        "registration_number":incoming_msg["registerNumber"],
        "vehicle_calender_availability": "",
        "status": "active",
        "rc_certificate": incoming_msg['rcCertificateUrl'],
        "premit_certificate": incoming_msg["permitCertificateUrl"],
        "fitness_certificate": incoming_msg["fitnessCertificateUrl"],
        "insurance_certificate": incoming_msg["insuranceCertificateUrl"],
        "pollution_certificate": incoming_msg["pollutionCertificateUrl"]
        
    }

    if checkRegisterNumber:
        return "This registration Number already there", 400
    

    vehicles.insert_one(vehicle_dict)
    # print(driver['_id'])
    return "working....."





@app.route('/fetchTrips', methods=["GET"])
@token_required
def fetchTrips(current):
    # user = User.query.filter_by(id=user_id).first()
    trips = db['Driver'].find_one({'_id': ObjectId(current)})["trips"]
    # Check if user exists
    return json.loads(json_util.dumps(trips)), 200


@app.route('/updateTripStatus', methods=['POST'])
@token_required
def updateTripStatus(currentUser):
    user_id = currentUser
    print(user_id)
    incoming_msg = request.get_json()
    bookingId = incoming_msg['bookingId']
    
    db['Driver'].update_many({
        "trips.bookingId": ObjectId(bookingId)
    }, {"$set":{"trips.$.trip_status":incoming_msg['status']}})

    return "working...."

@app.route('/getPrice', methods=['POST'])
def getPrice():
    incoming_msg = request.get_json()["Body"];
    # print(type(durationMinutes))
    origin = incoming_msg['origin_zone']
    destination = incoming_msg['destination']
    tripType = incoming_msg['trip_type']
    userFirstName = incoming_msg['user_id']
    zoneName = incoming_msg['origin_zone']
    zone = db['Zone']
    user = db['Customer'].find_one({"firstname": userFirstName})

    my_dist = gmaps.distance_matrix(origin,destination)['rows'][0]['elements'][0]
    distance = my_dist['distance']['text'].split(' ')[0]
    clearDistance = distance.replace(',', '') if ',' in distance else distance
    
    durationHours = my_dist['duration']['text'].split(' ')[0] if tripType == 'oneWay' else incoming_msg['trip_duration'].split(' ')[0]
    durationMinutes = my_dist['duration']['text'].split(' ')[2] if tripType == 'oneWay' else incoming_msg['trip_duration'].split(' ')[2]
    allDuration = int(durationHours) if int(durationMinutes) == 0 else int(durationHours) + 1
    
    # print(clearDistance)
    if user:
        price = calculateOneWayPricing(zoneName, int(clearDistance), allDuration, tripType)
        
        payload = {
         'originZone': zoneName,
        'toLocation': destination,
        'duration': allDuration,
        'distance': int(distance),
        "price": price

        }
        db['Customer'].update_one(
            {'firstname': user['firstname']},
            {
                "$push": {
                    "search_history": payload
                }
            }
            )
        return payload

    else:
        price = calculateOneWayPricing(zoneName, int(clearDistance), allDuration, tripType)
        payload = {
         'originZone': zoneName,
        'toLocation': destination,
        'duration': allDuration,
        'distance': distance,
        "price": price

    }
        return  payload
    
    

    # print(zoneName)

    # print()
    # return price

def calculateOneWayPricing(nameZone, distance, duration, trip):
    zone = db["Zone"]
    name = nameZone.upper()
    zoneName = zone.find_one({'zone_name':name})
    # print(zoneName)
    vehicles = db['Vehicles'].find({"zone_id": zoneName['_id']})
    # print(list(vehicles))
    # pricePerKM = zoneName['price_per_km']
    # priceperKmRoundTrip = zoneName['price_perkm_round']
    price = {
        'SUV': '',
        'MUV': '',
        'Hatchback': '',
        'Sedan': ''
    }
    # print(distance, type(distance))
    cars = []
    for i in list(vehicles):
        # print(i['vehicle_type'])
        cars.append(i['vehicle_type'])
    # type = cars.find_one({"vehicle_type": car})
    # cars = ['SUV', 'MUV', 'Hatchback', 'Sedan']
    print(cars)
    if trip == 'oneWay':
        for i in cars:
            for j in zoneName[i]['hourly_price']:
                # print( type(j['from']), type(j['to']))
                r = range(int(j['from']), int(j['to']))
                if duration in r:
                    # print(int(zoneName[i]['price_per_km']))
                    price[i] = (int(j['price']) * duration) + (int(zoneName[i]['price_per_km']) * distance)
    elif trip == 'roundTrip':
        for i in cars:
            for j in zoneName[i + "_round"]['hourly_price_round']:
                
                # print( type(j['from']), type(j['to']))
                r = range(int(j['from']), int(j['to']))
                if duration in r:
                    print(duration)
                    price[i] = (int(j['price']) * duration) + (int(zoneName[i + "_round"]['price_perkm_round']) * distance)


    return price

    
    
    # if duration >= type['from'] and duration <= type['to']:
    #     return type['price_per_hour'] * duration + (int(type['cost_per_km_one_way']) * distance)
    # elif duration >=12 and duration <=18:
    #     return (150 * 2) * duration + (int(type['cost_per_km_one_way']) * distance)
    # elif duration >18 and duration <= 24:
    #     return (125 * 2) * duration + (int(type['cost_per_km_one_way']) * distance)
            # return "hour price double * duration, + cost perkm * durationkm + "


def calculateTwoWayPricing(car, distance, duration):
    cars = db["Vehicles"]
    type = cars.find_one({"vehicle_type": car})
    # print(type['vehicle_type'])
    
    if type['vehicle_type'] == "Sedan" or type['vehicle_type'] == 'SUV' or type['vehicle_type'] == 'MUV' or type['vehicle_type'] == 'Hatchback':
        if duration >=1 and duration <=12:
            return 165 * duration + (int(type['cost_per_km_one_way']) * distance)
        elif duration >=12 and duration <=18:
            return 150 * duration + (int(type['cost_per_km_one_way']) * distance)
        elif duration >18 and duration <= 24:
            return 125 * duration + (int(type['cost_per_km_one_way']) * distance)

if __name__ == '__main__':
    app.run()
