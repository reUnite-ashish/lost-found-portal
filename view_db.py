from flask import Flask
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

# Create Flask app for context
app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/reunite_db'
mongo = PyMongo(app)

with app.app_context():
    def view_database():
        print("=== REUNITE DATABASE VIEWER ===\n")

        # Users
        print("USERS:")
        users = list(mongo.db.users.find())
        for user in users:
            print(f"  ID: {user['_id']}, Username: {user['username']}, Email: {user['email']}, Admin: {user.get('is_admin', False)}")
        print()

        # Items
        print("ITEMS:")
        items = list(mongo.db.items.find())
        for item in items:
            print(f"  ID: {item['_id']}, Name: {item['name']}, Type: {item['type']}, Status: {item['status']}")
        print()

        # Claims
        print("CLAIMS:")
        claims = list(mongo.db.claims.find())
        for claim in claims:
            print(f"  ID: {claim['_id']}, Item: {claim['item_name']}, Claimant: {claim['claimant_name']}, Status: {claim['status']}")
        print()

        # Found Matches
        print("FOUND MATCHES:")
        matches = list(mongo.db.found_matches.find())
        for match in matches:
            print(f"  ID: {match['_id']}, Lost Item: {match['lost_item_id']}, Finder: {match['finder_name']}, Status: {match['status']}")
        print()

        # Contact Requests
        print("CONTACT REQUESTS:")
        contacts = list(mongo.db.contact_requests.find())
        for contact in contacts:
            print(f"  ID: {contact['_id']}, From: {contact['from_username']}, To: {contact['to_username']}, Status: {contact['status']}")
        print()

        # Notifications
        print("NOTIFICATIONS:")
        notifs = list(mongo.db.notifications.find())
        for notif in notifs:
            print(f"  ID: {notif['_id']}, User: {notif['user_id']}, Message: {notif['message'][:50]}...")
        print()

    view_database()