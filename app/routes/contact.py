from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.contact_service import ContactService
from datetime import datetime
from app.utils.decorators import validate_json
from bson.objectid import ObjectId

bp = Blueprint('contact', __name__)

@bp.route('/send', methods=['POST'])
@validate_json({
    'name': {'type': 'string', 'required': True, 'minlength': 2},
    'email': {'type': 'string', 'required': True, 'regex': r'^[^@]+@[^@]+\.[^@]+$'},
    'subject': {'type': 'string', 'required': True, 'minlength': 5},
    'message': {'type': 'string', 'required': True, 'minlength': 10}
})
def send_message():
    data = request.get_json()
    mongo = current_app.mongo
    contacts = mongo.db.contact_messages

    message_doc = {
        "name": data['name'],
        "email": data['email'],
        "subject": data['subject'],
        "message": data['message'],
        "created_at": datetime.utcnow(),
        "is_read": False
    }

    result = contacts.insert_one(message_doc)
    message_doc['_id'] = result.inserted_id

    try:
        ContactService.send_notification_email(message_doc)
    except Exception as e:
        current_app.logger.error(f"Failed to send contact email: {str(e)}")

    return jsonify({
        'success': True,
        'message': 'Your message has been sent successfully'
    }), 201


@bp.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    user_id = get_jwt_identity()
    mongo = current_app.mongo
    users = mongo.db.users
    current_user = users.find_one({"_id": ObjectId(user_id)})

    if not current_user or not current_user.get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403

    limit = request.args.get('limit', 10, type=int)
    page = request.args.get('page', 1, type=int)
    skip = (page - 1) * limit

    contacts = mongo.db.contact_messages
    total = contacts.count_documents({})
    cursor = contacts.find().sort("created_at", -1).skip(skip).limit(limit)

    messages = [{
        'id': str(msg['_id']),
        'name': msg['name'],
        'email': msg['email'],
        'subject': msg['subject'],
        'created_at': msg['created_at'].isoformat(),
        'is_read': msg.get('is_read', False)
    } for msg in cursor]

    return jsonify({
        'messages': messages,
        'total': total,
        'pages': (total + limit - 1) // limit,
        'current_page': page
    })


@bp.route('/messages/<message_id>', methods=['GET', 'PUT'])
@jwt_required()
@validate_json({
    'is_read': {'type': 'boolean', 'required': False}
})
def manage_message(message_id):
    user_id = get_jwt_identity()
    mongo = current_app.mongo
    users = mongo.db.users
    current_user = users.find_one({"_id": ObjectId(user_id)})

    if not current_user or not current_user.get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403

    contacts = mongo.db.contact_messages
    try:
        msg_obj_id = ObjectId(message_id)
    except Exception:
        return jsonify({'error': 'Invalid message ID'}), 400

    message = contacts.find_one({"_id": msg_obj_id})
    if not message:
        return jsonify({'error': 'Message not found'}), 404

    if request.method == 'GET':
        if not message.get('is_read', False):
            contacts.update_one({"_id": msg_obj_id}, {"$set": {"is_read": True}})

        return jsonify({
            'id': str(message['_id']),
            'name': message['name'],
            'email': message['email'],
            'subject': message['subject'],
            'message': message['message'],
            'created_at': message['created_at'].isoformat(),
            'is_read': True
        })

    elif request.method == 'PUT':
        data = request.get_json()
        update_fields = {}
        if 'is_read' in data:
            update_fields['is_read'] = data['is_read']
            update_fields['updated_at'] = datetime.utcnow()

        if update_fields:
            contacts.update_one({"_id": msg_obj_id}, {"$set": update_fields})

        return jsonify({
            'success': True,
            'message': 'Message updated'
        })
