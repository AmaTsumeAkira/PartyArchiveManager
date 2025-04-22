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

    # Insert initial data with updated timeline (2025)
    users = [
        ('2025210101', '张三', generate_password_hash('sxcz123456'), '计算机2501班', '2025年第一期', 0),
        ('2025210102', '李华', generate_password_hash('sxcz123456'), '计算机2501班', '2025年第一期', 0),
        ('admin', '管理员', generate_password_hash('sxcz123456'), '无', None, 1)
    ]
    c.executemany('INSERT INTO users (student_id, name, password, class_name, batch, is_admin) VALUES (?, ?, ?, ?, ?, ?)', users)

    # 政治身份类型
    identities = [
        ('共青团员',),
        ('入党积极分子',),
        ('发展对象',),
        ('中共预备党员',),
        ('中共正式党员',)
    ]
    c.executemany('INSERT INTO identities (name) VALUES (?)', identities)

    # 用户身份关联 (张三:共青团员+积极分子; 李华:预备党员)
    user_identities = [
        (1, 1),  # 张三: 共青团员 (2023年9月入团)
        (1, 2),  # 张三: 入党积极分子 (2024年3月成为积极分子)
        (2, 4),  # 李华: 中共预备党员 (2025年1月成为预备党员)
    ]
    c.executemany('INSERT INTO user_identities (user_id, identity_id) VALUES (?, ?)', user_identities)

    # 所有可能的材料
    materials = [
        ('团员登记表',),
        ('推优表',),
        ('谈话记录表',),
        ('思想汇报',),
        ('入党申请书',),
        ('入党志愿书',),
        ('积极分子考察表',),
        ('党校结业证书',),
        ('政审材料',),
        ('转正申请书',),
        ('自传',),
        ('发展对象公示材料',),
        ('预备党员考察表',)
    ]
    c.executemany('INSERT INTO materials (name) VALUES (?)', materials)

    # 各身份对应的材料要求
    identity_materials = [
        # 共青团员
        (1, 1), (1, 2), (1, 4),
        
        # 入党积极分子
        (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 7), (2, 8),
        
        # 发展对象
        (3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (3, 11), (3, 12),
        
        # 中共预备党员
        (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (4, 11), (4, 13),
        
        # 中共正式党员
        (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 13)
    ]
    c.executemany('INSERT INTO identity_materials (identity_id, material_id) VALUES (?, ?)', identity_materials)

    # 用户材料状态
    # 张三(积极分子)的材料
    user_materials = [
        (1, 1, '齐全', '2023年9月入团时填写'),
        (1, 2, '齐全', '2024年1月推优通过'),
        (1, 3, '齐全', '2024年3月谈话记录'),
        (1, 4, '齐全', '2024年3月-2025年3月共5篇思想汇报'),
        (1, 5, '齐全', '2024年2月提交'),
        (1, 7, '齐全', '2024年3月-2025年3月考察记录'),
        (1, 8, '齐全', '2024年7月获得'),
        (1, 6, '待填写', '拟发展对象阶段填写'),
        (1, 9, '待准备', '拟发展对象阶段准备'),
        
        # 李华(预备党员)的材料
        (2, 1, '齐全', '2022年9月入团'),
        (2, 2, '齐全', '2024年3月推优'),
        (2, 3, '齐全', '2024年4月谈话记录'),
        (2, 4, '齐全', '2024年3月-2025年1月共6篇思想汇报'),
        (2, 5, '齐全', '2024年2月提交'),
        (2, 6, '齐全', '2025年1月填写'),
        (2, 7, '齐全', '2024年3月-2024年12月考察记录'),
        (2, 8, '齐全', '2024年7月获得'),
        (2, 9, '齐全', '2024年12月完成'),
        (2, 11, '齐全', '2024年10月提交'),
        (2, 13, '进行中', '2025年1月-2025年12月考察期')
    ]
    c.executemany('INSERT INTO user_materials (user_id, material_id, status, details) VALUES (?, ?, ?, ?)', user_materials)

    # 培养人信息
    cultivators = [
        ('王书记', '党支部书记'),
        ('李老师', '辅导员'),
        ('赵委员', '组织委员'),
        ('钱教授', '培养联系人'),
        ('孙同学', '党员联系人')
    ]
    c.executemany('INSERT INTO cultivators (name, role) VALUES (?, ?)', cultivators)

    # 用户与培养人关联
    user_cultivators = [
        (1, 1), (1, 2), (1, 4),  # 张三的培养人
        (2, 1), (2, 3), (2, 5)    # 李华的培养人
    ]
    c.executemany('INSERT INTO user_cultivators (user_id, cultivator_id) VALUES (?, ?)', user_cultivators)

    # 转接状态
    transfer_status = [
        (1, '材料准备中', '待确认', '2025-04-15', '计算机学院党支部', 60, None),  # 张三
        (2, '已转出', '已接收', '2025-03-20', '计算机学院党委', 100, None)     # 李华
    ]
    c.executemany('''
        INSERT INTO transfer_status (user_id, transfer_status, receive_status, transfer_date, receiver, progress, abandoned_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', transfer_status)

    # 公告
    announcements = [
        (1, '【重要通知】2025年发展对象材料提交截止时间为5月30日，请按时完成。', '2025-04-10'),
        (2, '2025年第一期党校培训将于4月20日开始，请报名同学准时参加。', '2025-04-05')
    ]
    c.executemany('INSERT INTO announcements (id, content, update_date) VALUES (?, ?, ?)', announcements)

    # 联系方式
    c.execute('INSERT INTO contact_info (id, phone) VALUES (1, "010-82345678")')
    c.execute('INSERT INTO contact_info (id, phone) VALUES (2, "010-82345679")')

    # 帮助内容
    c.execute('''
        INSERT INTO help_content (id, content)
        VALUES (1, '党员发展流程咨询：王老师 010-82345678\n档案转接问题：李老师 010-82345679')
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully with 2025 timeline data.")