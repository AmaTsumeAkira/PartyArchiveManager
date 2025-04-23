import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

def init_db():
    conn = sqlite3.connect('archive.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Drop existing tables
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS identities')
    c.execute('DROP TABLE IF EXISTS user_identities')
    c.execute('DROP TABLE IF EXISTS materials')
    c.execute('DROP TABLE IF EXISTS identity_materials')
    c.execute('DROP TABLE IF EXISTS user_materials')
    c.execute('DROP TABLE IF EXISTS transfer_status')
    c.execute('DROP TABLE IF EXISTS signatures')
    c.execute('DROP TABLE IF EXISTS announcements')
    c.execute('DROP TABLE IF EXISTS contact_info')
    c.execute('DROP TABLE IF EXISTS help_content')
    c.execute('DROP TABLE IF EXISTS cultivators')
    c.execute('DROP TABLE IF EXISTS user_cultivators')

    # Create tables
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            class_name TEXT NOT NULL,
            batch TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    c.execute('''
        CREATE TABLE user_identities (
            user_id INTEGER,
            identity_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (identity_id) REFERENCES identities(id),
            PRIMARY KEY (user_id, identity_id)
        )
    ''')

    c.execute('''
        CREATE TABLE materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    c.execute('''
        CREATE TABLE identity_materials (
            identity_id INTEGER,
            material_id INTEGER,
            FOREIGN KEY (identity_id) REFERENCES identities(id),
            FOREIGN KEY (material_id) REFERENCES materials(id),
            PRIMARY KEY (identity_id, material_id)
        )
    ''')

    c.execute('''
        CREATE TABLE user_materials (
            user_id INTEGER,
            material_id INTEGER,
            status TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (material_id) REFERENCES materials(id),
            PRIMARY KEY (user_id, material_id)
        )
    ''')

    c.execute('''
        CREATE TABLE transfer_status (
            user_id INTEGER PRIMARY KEY,
            transfer_status TEXT NOT NULL,
            receive_status TEXT NOT NULL,
            transfer_date TEXT,
            receiver TEXT,
            progress INTEGER NOT NULL,
            abandoned_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            signature_data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE announcements (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            update_date TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE contact_info (
            id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE help_content (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE cultivators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE user_cultivators (
            user_id INTEGER,
            cultivator_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (cultivator_id) REFERENCES cultivators(id),
            PRIMARY KEY (user_id, cultivator_id)
        )
    ''')

    # Insert only admin user
    admin_user = [
        ('admin', '管理员', generate_password_hash('sxcz123456'), '无', None, 1)
    ]
    c.executemany('INSERT INTO users (student_id, name, password, class_name, batch, is_admin) VALUES (?, ?, ?, ?, ?, ?)', admin_user)

    # Insert political identity types
    identities = [
        ('共青团员',),
        ('入党积极分子',),
        ('发展对象',),
        ('中共预备党员',),
        ('中共正式党员',)
    ]
    c.executemany('INSERT INTO identities (name) VALUES (?)', identities)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully with admin account and political identity types.")
