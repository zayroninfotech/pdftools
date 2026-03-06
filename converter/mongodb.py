"""
MongoDB integration layer for PDFTools.

Uses pymongo to connect directly to MongoDB (database: pdftools).
Syncs data from Django ORM models into MongoDB collections for:
  - users
  - usage_logs
  - anonymous_sessions
  - audit_trail
  - signature_records

Django ORM (SQLite) remains the primary source for auth/sessions.
MongoDB acts as the persistent document store for all application data.
"""

import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── SINGLETON CONNECTION ──────────────────────────────────────────────────────

_client = None
_db = None


def get_client():
    """Get or create the pymongo MongoClient singleton."""
    global _client
    if _client is None:
        try:
            from pymongo import MongoClient
            uri = getattr(settings, 'MONGODB_URI', 'mongodb://localhost:27017')
            _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Test connection
            _client.admin.command('ping')
            logger.info(f"MongoDB connected: {uri}")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e}")
            _client = None
    return _client


def get_db():
    """Get the pdftools MongoDB database."""
    global _db
    if _db is None:
        client = get_client()
        if client:
            db_name = getattr(settings, 'MONGODB_NAME', 'pdftools')
            _db = client[db_name]
    return _db


def is_connected():
    """Check if MongoDB is available."""
    try:
        client = get_client()
        if client:
            client.admin.command('ping')
            return True
    except Exception:
        pass
    return False


# ─── COLLECTION HELPERS ────────────────────────────────────────────────────────

def _get_collection(name):
    """Get a MongoDB collection by name. Returns None if not connected."""
    db = get_db()
    if db is not None:
        return db[name]
    return None


# ─── EMAIL SUBMISSIONS ────────────────────────────────────────────────────────

def store_email(email, ip_address=None, user_agent='', session_key=''):
    """
    Store a submitted email address in MongoDB 'email_submissions' collection.
    Auto-creates the collection if it doesn't exist.
    Returns the inserted document ID, or None if MongoDB is unavailable.
    """
    collection = _get_collection('email_submissions')
    if collection is None:
        return None

    try:
        # Check if this email already exists
        existing = collection.find_one({'email': email})
        if existing:
            # Update last_seen and visit count
            result = collection.update_one(
                {'email': email},
                {
                    '$set': {
                        'last_seen': datetime.utcnow(),
                        'last_ip': ip_address,
                        'last_user_agent': user_agent,
                    },
                    '$inc': {'visit_count': 1},
                    '$addToSet': {'session_keys': session_key},
                }
            )
            logger.info(f"MongoDB: Email '{email}' updated (visit #{existing.get('visit_count', 0) + 1})")
            return existing.get('_id')
        else:
            # New email submission
            doc = {
                'email': email,
                'first_seen': datetime.utcnow(),
                'last_seen': datetime.utcnow(),
                'ip_address': ip_address,
                'last_ip': ip_address,
                'user_agent': user_agent,
                'last_user_agent': user_agent,
                'session_keys': [session_key] if session_key else [],
                'visit_count': 1,
                'source': 'email_popup',
            }
            result = collection.insert_one(doc)
            logger.info(f"MongoDB: New email '{email}' stored in email_submissions")
            return result.inserted_id
    except Exception as e:
        logger.warning(f"MongoDB: Failed to store email '{email}': {e}")
        return None


def get_all_emails(limit=500):
    """
    Retrieve all submitted emails from MongoDB.
    Returns list of email docs or None if not connected.
    """
    collection = _get_collection('email_submissions')
    if collection is None:
        return None
    try:
        return list(collection.find().sort('last_seen', -1).limit(limit))
    except Exception as e:
        logger.warning(f"MongoDB: Failed to get emails: {e}")
        return None


# ─── ENSURE INDEXES ────────────────────────────────────────────────────────────

def ensure_indexes():
    """Create indexes on MongoDB collections for optimal query performance."""
    try:
        db = get_db()
        if db is None:
            return

        # Users collection indexes
        db.users.create_index('username', unique=True)
        db.users.create_index('email')
        db.users.create_index('role')
        db.users.create_index('is_active')

        # Usage logs indexes
        db.usage_logs.create_index([('user_id', 1), ('created_at', -1)])
        db.usage_logs.create_index([('session_key', 1), ('email', 1)])
        db.usage_logs.create_index('created_at')
        db.usage_logs.create_index('tool_name')

        # Anonymous sessions indexes
        db.anonymous_sessions.create_index(
            [('email', 1), ('session_key', 1)], unique=True
        )

        # Audit trail indexes
        db.audit_trail.create_index([('action', 1), ('timestamp', -1)])
        db.audit_trail.create_index([('user_id', 1), ('timestamp', -1)])
        db.audit_trail.create_index('email')
        db.audit_trail.create_index('timestamp')

        # Signature records indexes
        db.signature_records.create_index([('signer_email', 1), ('signed_at', -1)])
        db.signature_records.create_index('document_name')
        db.signature_records.create_index('signature_id')

        # Email submissions indexes
        db.email_submissions.create_index('email', unique=True)
        db.email_submissions.create_index('last_seen')
        db.email_submissions.create_index('first_seen')

        logger.info("MongoDB indexes created successfully.")
    except Exception as e:
        logger.warning(f"MongoDB index creation failed: {e}")


# ─── USER SYNC ─────────────────────────────────────────────────────────────────

def sync_user(user):
    """
    Sync a Django CustomUser instance to MongoDB users collection.
    Called after user creation or update.
    """
    collection = _get_collection('users')
    if collection is None:
        return None

    try:
        doc = {
            'django_id': user.pk,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'phone': getattr(user, 'phone', ''),
            'company': getattr(user, 'company', ''),
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'created_at': getattr(user, 'created_at', None),
            'updated_at': datetime.utcnow(),
        }

        result = collection.update_one(
            {'django_id': user.pk},
            {'$set': doc},
            upsert=True
        )
        logger.info(f"MongoDB: User '{user.username}' synced (upsert={result.upserted_id is not None})")
        return result
    except Exception as e:
        logger.warning(f"MongoDB: Failed to sync user '{user.username}': {e}")
        return None


def sync_user_deletion(user):
    """
    Mark a user as inactive in MongoDB (soft delete).
    """
    collection = _get_collection('users')
    if collection is None:
        return None

    try:
        result = collection.update_one(
            {'django_id': user.pk},
            {'$set': {
                'is_active': False,
                'updated_at': datetime.utcnow(),
                'deactivated_at': datetime.utcnow(),
            }}
        )
        logger.info(f"MongoDB: User '{user.username}' deactivated")
        return result
    except Exception as e:
        logger.warning(f"MongoDB: Failed to deactivate user: {e}")
        return None


def get_all_users(role_filter=None, search=None, active_only=False):
    """
    Query users from MongoDB.
    Returns list of user dicts.
    """
    collection = _get_collection('users')
    if collection is None:
        return None  # Caller falls back to Django ORM

    try:
        query = {}
        if role_filter:
            query['role'] = role_filter
        if active_only:
            query['is_active'] = True
        if search:
            query['$or'] = [
                {'username': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'first_name': {'$regex': search, '$options': 'i'}},
                {'last_name': {'$regex': search, '$options': 'i'}},
            ]
        return list(collection.find(query).sort('created_at', -1))
    except Exception as e:
        logger.warning(f"MongoDB: Failed to query users: {e}")
        return None


# ─── USAGE LOG SYNC ────────────────────────────────────────────────────────────

def log_usage(user=None, session_key='', email='', tool_name='',
              filename='', file_size=0, ip_address=None, user_agent='',
              success=True):
    """
    Log a tool usage event to MongoDB usage_logs collection.
    """
    collection = _get_collection('usage_logs')
    if collection is None:
        return None

    try:
        doc = {
            'user_id': user.pk if user else None,
            'username': user.username if user else None,
            'session_key': session_key,
            'email': email,
            'tool_name': tool_name,
            'filename': filename,
            'file_size': file_size,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'created_at': datetime.utcnow(),
        }
        result = collection.insert_one(doc)
        return result.inserted_id
    except Exception as e:
        logger.warning(f"MongoDB: Failed to log usage: {e}")
        return None


# ─── ANONYMOUS SESSION SYNC ───────────────────────────────────────────────────

def sync_anonymous_session(email, session_key, usage_count, ip_address=None):
    """
    Sync anonymous session data to MongoDB.
    """
    collection = _get_collection('anonymous_sessions')
    if collection is None:
        return None

    try:
        result = collection.update_one(
            {'email': email, 'session_key': session_key},
            {
                '$set': {
                    'usage_count': usage_count,
                    'ip_address': ip_address,
                    'last_used': datetime.utcnow(),
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow(),
                }
            },
            upsert=True
        )
        return result
    except Exception as e:
        logger.warning(f"MongoDB: Failed to sync anonymous session: {e}")
        return None


# ─── AUDIT TRAIL SYNC ─────────────────────────────────────────────────────────

def log_audit(audit_id, user=None, email='', username='', action='',
              detail='', document_name='', ip_address=None, user_agent='',
              timestamp=None, checksum=''):
    """
    Sync an audit trail entry to MongoDB audit_trail collection.
    """
    collection = _get_collection('audit_trail')
    if collection is None:
        return None

    try:
        doc = {
            'audit_id': str(audit_id),
            'user_id': user.pk if user else None,
            'email': email,
            'username': username,
            'action': action,
            'detail': detail,
            'document_name': document_name,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': timestamp or datetime.utcnow(),
            'checksum': checksum,
        }
        result = collection.insert_one(doc)
        return result.inserted_id
    except Exception as e:
        logger.warning(f"MongoDB: Failed to log audit: {e}")
        return None


def get_audit_logs(action_filter=None, limit=200):
    """
    Query audit trail from MongoDB.
    Returns list of audit dicts.
    """
    collection = _get_collection('audit_trail')
    if collection is None:
        return None

    try:
        query = {}
        if action_filter:
            query['action'] = action_filter
        return list(
            collection.find(query)
            .sort('timestamp', -1)
            .limit(limit)
        )
    except Exception as e:
        logger.warning(f"MongoDB: Failed to query audit logs: {e}")
        return None


# ─── SIGNATURE RECORD SYNC ────────────────────────────────────────────────────

def log_signature(sig_record):
    """
    Sync a SignatureRecord to MongoDB signature_records collection.
    """
    collection = _get_collection('signature_records')
    if collection is None:
        return None

    try:
        doc = {
            'signature_id': str(sig_record.id),
            'user_id': sig_record.user_id,
            'signer_name': sig_record.signer_name,
            'signer_email': sig_record.signer_email,
            'meaning': sig_record.meaning,
            'document_name': sig_record.document_name,
            'document_hash_before': sig_record.document_hash_before,
            'document_hash_after': sig_record.document_hash_after,
            'output_file': sig_record.output_file,
            'position_x': sig_record.position_x,
            'position_y': sig_record.position_y,
            'page_number': sig_record.page_number,
            'is_authenticated': sig_record.is_authenticated,
            'ip_address': str(sig_record.ip_address) if sig_record.ip_address else None,
            'user_agent': sig_record.user_agent,
            'signed_at': sig_record.signed_at or datetime.utcnow(),
            'record_checksum': sig_record.record_checksum,
        }
        result = collection.insert_one(doc)
        logger.info(f"MongoDB: Signature '{sig_record.id}' synced")
        return result.inserted_id
    except Exception as e:
        logger.warning(f"MongoDB: Failed to log signature: {e}")
        return None


def get_signature(signature_id):
    """
    Look up a signature record from MongoDB.
    """
    collection = _get_collection('signature_records')
    if collection is None:
        return None

    try:
        return collection.find_one({'signature_id': str(signature_id)})
    except Exception as e:
        logger.warning(f"MongoDB: Failed to get signature: {e}")
        return None


# ─── DASHBOARD / STATS ────────────────────────────────────────────────────────

def get_usage_stats():
    """
    Get usage statistics from MongoDB.
    Returns dict with total_users, total_usage, tool_breakdown.
    """
    db = get_db()
    if db is None:
        return None

    try:
        stats = {
            'total_users': db.users.count_documents({'is_active': True}),
            'total_usage': db.usage_logs.count_documents({'success': True}),
            'total_signatures': db.signature_records.count_documents({}),
            'total_anonymous': db.anonymous_sessions.count_documents({}),
        }

        # Tool usage breakdown
        pipeline = [
            {'$match': {'success': True}},
            {'$group': {'_id': '$tool_name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
        ]
        stats['tool_breakdown'] = list(db.usage_logs.aggregate(pipeline))

        return stats
    except Exception as e:
        logger.warning(f"MongoDB: Failed to get stats: {e}")
        return None


# ─── INITIAL SYNC ──────────────────────────────────────────────────────────────

def full_sync_from_django():
    """
    Full one-time sync of all Django ORM data to MongoDB.
    Useful for initial migration or data recovery.
    """
    from .models import CustomUser, UsageLog, AuditTrail, SignatureRecord, AnonymousSession

    if not is_connected():
        logger.error("MongoDB not available for full sync.")
        return False

    ensure_indexes()

    # Sync users
    for user in CustomUser.objects.all():
        sync_user(user)

    # Sync usage logs
    collection = _get_collection('usage_logs')
    if collection:
        for log_entry in UsageLog.objects.all():
            doc = {
                'django_id': log_entry.pk,
                'user_id': log_entry.user_id,
                'username': log_entry.user.username if log_entry.user else None,
                'session_key': log_entry.session_key,
                'email': log_entry.email,
                'tool_name': log_entry.tool_name,
                'filename': log_entry.filename,
                'file_size': log_entry.file_size,
                'ip_address': str(log_entry.ip_address) if log_entry.ip_address else None,
                'user_agent': log_entry.user_agent,
                'success': log_entry.success,
                'created_at': log_entry.created_at,
            }
            collection.update_one(
                {'django_id': log_entry.pk},
                {'$set': doc},
                upsert=True
            )

    # Sync audit trail
    collection = _get_collection('audit_trail')
    if collection:
        for audit in AuditTrail.objects.all():
            doc = {
                'audit_id': str(audit.id),
                'user_id': audit.user_id,
                'email': audit.email,
                'username': audit.username,
                'action': audit.action,
                'detail': audit.detail,
                'document_name': audit.document_name,
                'ip_address': str(audit.ip_address) if audit.ip_address else None,
                'user_agent': audit.user_agent,
                'timestamp': audit.timestamp,
                'checksum': audit.checksum,
            }
            collection.update_one(
                {'audit_id': str(audit.id)},
                {'$set': doc},
                upsert=True
            )

    # Sync signature records
    collection = _get_collection('signature_records')
    if collection:
        for sig in SignatureRecord.objects.all():
            log_signature(sig)

    # Sync anonymous sessions
    collection = _get_collection('anonymous_sessions')
    if collection:
        for anon in AnonymousSession.objects.all():
            sync_anonymous_session(
                email=anon.email,
                session_key=anon.session_key,
                usage_count=anon.usage_count,
                ip_address=str(anon.ip_address) if anon.ip_address else None,
            )

    logger.info("MongoDB: Full sync from Django completed.")
    return True
