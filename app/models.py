from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from bson.objectid import ObjectId


class User:
    def __init__(self, username, email, password_hash=None, api_key=None, is_admin=False, created_at=None, _id=None):
        self.id = _id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.api_key = api_key
        self.is_admin = is_admin
        self.created_at = created_at or datetime.utcnow()

    @staticmethod
    def collection():
        return current_app.mongo.db.users

    @staticmethod
    def find_by_username(username):
        data = User.collection().find_one({"username": username})
        if data:
            return User.from_dict(data)
        return None

    @staticmethod
    def find_by_email(email):
        data = User.collection().find_one({"email": email})
        if data:
            return User.from_dict(data)
        return None

    @staticmethod
    def find_by_id(user_id):
        data = User.collection().find_one({"_id": ObjectId(user_id)})
        if data:
            return User.from_dict(data)
        return None

    @staticmethod
    def from_dict(data):
        return User(
            username=data.get("username"),
            email=data.get("email"),
            password_hash=data.get("password_hash"),
            api_key=data.get("api_key"),
            is_admin=data.get("is_admin", False),
            created_at=data.get("created_at"),
            _id=str(data.get("_id"))
        )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def save(self):
        data = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "api_key": self.api_key,
            "is_admin": self.is_admin,
            "created_at": self.created_at,
        }
        if self.id:
            User.collection().update_one({"_id": ObjectId(self.id)}, {"$set": data})
        else:
            result = User.collection().insert_one(data)
            self.id = str(result.inserted_id)

    def delete(self):
        if self.id:
            User.collection().delete_one({"_id": ObjectId(self.id)})

    def __repr__(self):
        return f"<User {self.username}>"


class SearchHistory:
    def __init__(self, user_id, query, search_type=None, results_count=0, timestamp=None, source=None, _id=None):
        self.id = _id
        self.user_id = user_id
        self.query = query
        self.search_type = search_type
        self.results_count = results_count
        self.timestamp = timestamp or datetime.utcnow()
        self.source = source

    @staticmethod
    def collection():
        return current_app.mongo.db.search_history

    def save(self):
        data = {
            "user_id": ObjectId(self.user_id),
            "query": self.query,
            "search_type": self.search_type,
            "results_count": self.results_count,
            "timestamp": self.timestamp,
            "source": self.source,
        }
        if self.id:
            SearchHistory.collection().update_one({"_id": ObjectId(self.id)}, {"$set": data})
        else:
            result = SearchHistory.collection().insert_one(data)
            self.id = str(result.inserted_id)

    @staticmethod
    def from_dict(data):
        return SearchHistory(
            user_id=str(data.get("user_id")),
            query=data.get("query"),
            search_type=data.get("search_type"),
            results_count=data.get("results_count"),
            timestamp=data.get("timestamp"),
            source=data.get("source"),
            _id=str(data.get("_id"))
        )

    def __repr__(self):
        return f"<Search {self.query} by user {self.user_id}>"


class Favorite:
    def __init__(self, user_id, title, url, snippet=None, fav_type=None, added_at=None, tags=None, _id=None):
        self.id = _id
        self.user_id = user_id
        self.title = title
        self.url = url
        self.snippet = snippet
        self.fav_type = fav_type
        self.added_at = added_at or datetime.utcnow()
        self.tags = tags  # string comma-separated or list

    @staticmethod
    def collection():
        return current_app.mongo.db.favorites

    def save(self):
        data = {
            "user_id": ObjectId(self.user_id),
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "fav_type": self.fav_type,
            "added_at": self.added_at,
            "tags": self.tags,
        }
        if self.id:
            Favorite.collection().update_one({"_id": ObjectId(self.id)}, {"$set": data})
        else:
            result = Favorite.collection().insert_one(data)
            self.id = str(result.inserted_id)

    @staticmethod
    def from_dict(data):
        return Favorite(
            user_id=str(data.get("user_id")),
            title=data.get("title"),
            url=data.get("url"),
            snippet=data.get("snippet"),
            fav_type=data.get("fav_type"),
            added_at=data.get("added_at"),
            tags=data.get("tags"),
            _id=str(data.get("_id"))
        )

    def __repr__(self):
        return f"<Favorite {self.title} by user {self.user_id}>"


class ContactMessage:
    def __init__(self, name, email, subject, message, created_at=None, is_read=False, _id=None):
        self.id = _id
        self.name = name
        self.email = email
        self.subject = subject
        self.message = message
        self.created_at = created_at or datetime.utcnow()
        self.is_read = is_read

    @staticmethod
    def collection():
        return current_app.mongo.db.contact_messages

    def save(self):
        data = {
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "created_at": self.created_at,
            "is_read": self.is_read,
        }
        if self.id:
            ContactMessage.collection().update_one({"_id": ObjectId(self.id)}, {"$set": data})
        else:
            result = ContactMessage.collection().insert_one(data)
            self.id = str(result.inserted_id)

    @staticmethod
    def from_dict(data):
        return ContactMessage(
            name=data.get("name"),
            email=data.get("email"),
            subject=data.get("subject"),
            message=data.get("message"),
            created_at=data.get("created_at"),
            is_read=data.get("is_read", False),
            _id=str(data.get("_id"))
        )

    def __repr__(self):
        return f"<Message from {self.name} about {self.subject}>"


class SearchAnalytics:
    def __init__(self, date, total_searches=0, unique_users=0, avg_response_time=0, most_popular_query=None, _id=None):
        self.id = _id
        self.date = date
        self.total_searches = total_searches
        self.unique_users = unique_users
        self.avg_response_time = avg_response_time
        self.most_popular_query = most_popular_query

    @staticmethod
    def collection():
        return current_app.mongo.db.search_analytics

    def save(self):
        data = {
            "date": self.date,
            "total_searches": self.total_searches,
            "unique_users": self.unique_users,
            "avg_response_time": self.avg_response_time,
            "most_popular_query": self.most_popular_query,
        }
        if self.id:
            SearchAnalytics.collection().update_one({"_id": ObjectId(self.id)}, {"$set": data})
        else:
            result = SearchAnalytics.collection().insert_one(data)
            self.id = str(result.inserted_id)

    @staticmethod
    def from_dict(data):
        return SearchAnalytics(
            date=data.get("date"),
            total_searches=data.get("total_searches", 0),
            unique_users=data.get("unique_users", 0),
            avg_response_time=data.get("avg_response_time", 0),
            most_popular_query=data.get("most_popular_query"),
            _id=str(data.get("_id"))
        )

    def __repr__(self):
        return f"<Analytics for {self.date}>"
