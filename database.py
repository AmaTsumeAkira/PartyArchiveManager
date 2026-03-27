import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
import logging

# 配置日志记录器
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()         # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)

def get_db():
    conn = sqlite3.connect('archive.db', timeout=10)  # 增加超时时间
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_student_id(student_id):
    try:
        conn = get_db()
        with conn:
            user = conn.execute('SELECT * FROM users WHERE student_id = ?', (student_id,)).fetchone()
        return user
    finally:
        conn.close()

def get_user_identities(user_id):
    try:
        conn = get_db()
        with conn:
            identities = conn.execute('''
                SELECT i.id, i.name as identity_name
                FROM user_identities ui
                JOIN identities i ON ui.identity_id = i.id
                WHERE ui.user_id = ?
                ORDER BY i.id
            ''', (user_id,)).fetchall()
        return identities
    finally:
        conn.close()

def get_user_identity_ids(user_id):
    try:
        conn = get_db()
        with conn:
            identity_ids = conn.execute('SELECT identity_id FROM user_identities WHERE user_id = ?', (user_id,)).fetchall()
        return [i['identity_id'] for i in identity_ids]
    finally:
        conn.close()

def get_all_identities():
    try:
        conn = get_db()
        with conn:
            identities = conn.execute('SELECT id, name FROM identities ORDER BY id').fetchall()
        return identities
    finally:
        conn.close()

def update_user_identities(user_id, identity_ids):
    try:
        conn = get_db()
        with conn:
            conn.execute('DELETE FROM user_identities WHERE user_id = ?', (user_id,))
            for identity_id in identity_ids:
                conn.execute('INSERT OR IGNORE INTO user_identities (user_id, identity_id) VALUES (?, ?)',
                            (user_id, identity_id))
        initialize_user_materials(user_id)  # 确保材料记录更新
    finally:
        conn.close()

def update_user_materials_by_identities(user_id, identity_ids):
    try:
        conn = get_db()
        with conn:
            # 获取用户需要的材料
            materials = conn.execute('''
                SELECT DISTINCT m.id, m.name
                FROM identity_materials im
                JOIN materials m ON im.material_id = m.id
                WHERE im.identity_id IN ({})
            '''.format(','.join('?' * len(identity_ids))), identity_ids).fetchall()
            # 删除用户不再需要的材料
            conn.execute('''
                DELETE FROM user_materials
                WHERE user_id = ? AND material_id NOT IN (
                    SELECT material_id FROM identity_materials WHERE identity_id IN ({})
                )
            '''.format(','.join('?' * len(identity_ids))), [user_id] + identity_ids)
            # 为用户添加新材料
            for material in materials:
                exists = conn.execute('SELECT 1 FROM user_materials WHERE user_id = ? AND material_id = ?',
                                    (user_id, material['id'])).fetchone()
                if not exists:
                    conn.execute('INSERT INTO user_materials (user_id, material_id, status, details) VALUES (?, ?, ?, ?)',
                                (user_id, material['id'], '待审核', ''))
    finally:
        conn.close()

def get_user_materials(user_id):
    try:
        conn = get_db()
        with conn:
            materials = conn.execute('''
                SELECT DISTINCT m.id, m.name, 
                       COALESCE(um.status, '未录入') as status,
                       COALESCE(um.details, '') as details
                FROM materials m
                LEFT JOIN user_materials um ON m.id = um.material_id AND um.user_id = ?
                WHERE EXISTS (
                    SELECT 1 FROM identity_materials im 
                    JOIN user_identities ui ON im.identity_id = ui.identity_id
                    WHERE ui.user_id = ? AND im.material_id = m.id
                )
                ORDER BY m.id
            ''', (user_id, user_id)).fetchall()
        return materials
    finally:
        conn.close()

def initialize_user_materials(user_id):
    try:
        conn = get_db()
        with conn:
            # 获取用户身份
            identity_ids = get_user_identity_ids(user_id)
            if not identity_ids:
                return
            # 获取身份所需的材料
            materials = conn.execute('''
                SELECT DISTINCT m.id, m.name
                FROM identity_materials im
                JOIN materials m ON im.material_id = m.id
                WHERE im.identity_id IN ({})
            '''.format(','.join('?' * len(identity_ids))), identity_ids).fetchall()
            # 为用户添加缺失的材料记录
            for material in materials:
                exists = conn.execute('''
                    SELECT 1 FROM user_materials WHERE user_id = ? AND material_id = ?
                ''', (user_id, material['id'])).fetchone()
                if not exists:
                    conn.execute('''
                        INSERT INTO user_materials (user_id, material_id, status, details)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, material['id'], '未录入', ''))
                    logger.debug(f"Initialized material for user_id={user_id}, material_id={material['id']}: status=未录入")
    finally:
        conn.close()

def get_user_cultivators(user_id):
    try:
        conn = get_db()
        with conn:
            cultivators = conn.execute('''
                SELECT c.id, c.name, c.role
                FROM user_cultivators uc
                JOIN cultivators c ON uc.cultivator_id = c.id
                WHERE uc.user_id = ?
                ORDER BY c.id
            ''', (user_id,)).fetchall()
        return cultivators
    finally:
        conn.close()

def get_transfer_status(user_id):
    try:
        conn = get_db()
        with conn:
            status = conn.execute('''
                SELECT transfer_status, receive_status, transfer_date, receiver, progress, abandoned_at
                FROM transfer_status
                WHERE user_id = ?
            ''', (user_id,)).fetchone()
        if status is None:
            return {
                'transfer_status': '未开始',
                'receive_status': '未开始',
                'transfer_date': None,
                'receiver': None,
                'progress': 0,
                'abandoned_at': None
            }
        return status
    finally:
        conn.close()

def update_transfer_status(user_id, transfer_status, receive_status, receiver=None, progress=0, transfer_date=None, abandoned=False):
    try:
        conn = get_db()
        with conn:
            exists = conn.execute('SELECT 1 FROM transfer_status WHERE user_id = ?', (user_id,)).fetchone()
            if abandoned:
                if exists:
                    conn.execute('''
                        UPDATE transfer_status
                        SET transfer_status = ?, receive_status = ?, progress = 0, 
                            abandoned_at = ?, receiver = ?, transfer_date = ?
                        WHERE user_id = ?
                    ''', (transfer_status, receive_status, 
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                          receiver, transfer_date, user_id))
                else:
                    conn.execute('''
                        INSERT INTO transfer_status (user_id, transfer_status, receive_status, 
                                                  progress, abandoned_at, receiver, transfer_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, transfer_status, receive_status, 0, 
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                          receiver, transfer_date))
            else:
                if exists:
                    conn.execute('''
                        UPDATE transfer_status
                        SET transfer_status = ?, receive_status = ?, 
                            receiver = ?, progress = ?, transfer_date = ?
                        WHERE user_id = ?
                    ''', (transfer_status, receive_status, receiver, progress, transfer_date, user_id))
                else:
                    conn.execute('''
                        INSERT INTO transfer_status (user_id, transfer_status, receive_status, 
                                                  receiver, progress, transfer_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, transfer_status, receive_status, receiver, progress, transfer_date))
    finally:
        conn.close()


def save_signature(user_id, signature_data):
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                INSERT INTO signatures (user_id, signature_data, created_at)
                VALUES (?, ?, ?)
            ''', (user_id, signature_data, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    finally:
        conn.close()

def get_user_signature(user_id):
    try:
        conn = get_db()
        with conn:
            signature = conn.execute('''
                SELECT signature_data, created_at
                FROM signatures
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,)).fetchone()
        return signature
    finally:
        conn.close()

def get_abandoned_users():
    try:
        conn = get_db()
        with conn:
            users = conn.execute('''
                SELECT u.student_id, u.name, u.id, ts.abandoned_at
                FROM users u
                JOIN transfer_status ts ON u.id = ts.user_id
                WHERE ts.transfer_status = '已放弃'
            ''').fetchall()
        return users
    finally:
        conn.close()

def update_material_status(user_id, material_id, status):
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                UPDATE user_materials
                SET status = ?
                WHERE user_id = ? AND material_id = ?
            ''', (status, user_id, material_id))
    finally:
        conn.close()

def add_or_update_user_material(user_id, material_id, status, details):
    try:
        conn = get_db()
        with conn:
            exists = conn.execute('''
                SELECT 1 FROM user_materials WHERE user_id = ? AND material_id = ?
            ''', (user_id, material_id)).fetchone()
            if exists:
                conn.execute('''
                    UPDATE user_materials
                    SET status = ?, details = ?
                    WHERE user_id = ? AND material_id = ?
                ''', (status, details, user_id, material_id))
            else:
                conn.execute('''
                    INSERT INTO user_materials (user_id, material_id, status, details)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, material_id, status, details))
    finally:
        conn.close()

def get_material_requirements(identity_id):
    try:
        conn = get_db()
        with conn:
            materials = conn.execute('''
                SELECT DISTINCT m.id, m.name
                FROM identity_materials im
                JOIN materials m ON im.material_id = m.id
                WHERE im.identity_id <= ?
                ORDER BY m.id
            ''', (identity_id,)).fetchall()
        return materials
    finally:
        conn.close()

def update_material_requirements(identity_id, materials):
    try:
        conn = get_db()
        with conn:
            identity_id = int(identity_id) if isinstance(identity_id, str) else identity_id
            # 删除当前身份的材料关联
            conn.execute('DELETE FROM identity_materials WHERE identity_id = ?', (identity_id,))
            # 获取低等级身份的材料
            required_materials = set(m.strip().lower() for m in materials if m.strip())
            if identity_id > 1:
                lower_materials = conn.execute('''
                    SELECT DISTINCT m.name
                    FROM identity_materials im
                    JOIN materials m ON im.material_id = m.id
                    WHERE im.identity_id < ? AND im.identity_id IN (1, 2, 3, 4)
                ''', (identity_id,)).fetchall()
                required_materials.update(m.lower() for m in [m['name'] for m in lower_materials])
            # 插入材料到 materials 表并关联到 identity_materials
            for material_name in required_materials:
                material_id = conn.execute('SELECT id FROM materials WHERE LOWER(name) = ?', (material_name,)).fetchone()
                if not material_id:
                    conn.execute('INSERT INTO materials (name) VALUES (?)', (material_name.capitalize(),))
                    material_id = conn.execute('SELECT id FROM materials WHERE LOWER(name) = ?', (material_name,)).fetchone()
                exists = conn.execute('SELECT 1 FROM identity_materials WHERE identity_id = ? AND material_id = ?',
                                     (identity_id, material_id['id'])).fetchone()
                if not exists:
                    conn.execute('INSERT INTO identity_materials (identity_id, material_id) VALUES (?, ?)',
                                (identity_id, material_id['id']))
            # 为当前和高等级身份的用户分配材料
            for id_id in range(1, 5):
                users = conn.execute('SELECT user_id FROM user_identities WHERE identity_id = ?', (id_id,)).fetchall()
                for user in users:
                    for material_name in required_materials:
                        material_id = conn.execute('SELECT id FROM materials WHERE LOWER(name) = ?', (material_name,)).fetchone()['id']
                        exists = conn.execute('SELECT 1 FROM user_materials WHERE user_id = ? AND material_id = ?',
                                            (user['user_id'], material_id)).fetchone()
                        if not exists:
                            conn.execute('INSERT INTO user_materials (user_id, material_id, status, details) VALUES (?, ?, ?, ?)',
                                        (user['user_id'], material_id, '待审核', ''))
            # 清理不再需要的用户材料
            conn.execute('''
                DELETE FROM user_materials
                WHERE material_id NOT IN (
                    SELECT material_id FROM identity_materials WHERE identity_id = ?
                ) AND user_id IN (
                    SELECT user_id FROM user_identities WHERE identity_id = ?
                )
            ''', (identity_id, identity_id))
    finally:
        conn.close()

def delete_material(material_id, identity_id):
    try:
        conn = get_db()
        with conn:
            # 检查材料是否存在
            material = conn.execute('SELECT name FROM materials WHERE id = ?', (material_id,)).fetchone()
            if not material:
                return {'success': False, 'error': '材料不存在'}
            # 检查材料是否属于当前身份
            exists = conn.execute('''
                SELECT 1 FROM identity_materials
                WHERE material_id = ? AND identity_id = ?
            ''', (material_id, identity_id)).fetchone()
            if not exists:
                return {'success': False, 'error': f'材料“{material["name"]}”不属于该身份'}
            # 删除当前身份及高等级身份的 identity_materials 记录
            conn.execute('''
                DELETE FROM identity_materials
                WHERE material_id = ? AND identity_id >= ?
            ''', (material_id, identity_id))
            # 删除所有用户的 user_materials 记录
            conn.execute('DELETE FROM user_materials WHERE material_id = ?', (material_id,))
            # 删除 materials 表中不再关联的记录
            conn.execute('''
                DELETE FROM materials
                WHERE id = ? AND id NOT IN (SELECT material_id FROM identity_materials)
            ''', (material_id,))
        return {'success': True}
    finally:
        conn.close()

def clean_unused_materials():
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                DELETE FROM materials
                WHERE id NOT IN (SELECT material_id FROM identity_materials)
            ''')
    finally:
        conn.close()

def get_announcement():
    try:
        conn = get_db()
        with conn:
            announcement = conn.execute('SELECT content, update_date FROM announcements WHERE id = 1').fetchone()
        return announcement
    finally:
        conn.close()

def update_announcement(content, update_date):
    try:
        conn = get_db()
        with conn:
            conn.execute('UPDATE announcements SET content = ?, update_date = ? WHERE id = 1',
                        (content, update_date))
    finally:
        conn.close()

def get_contact_info():
    try:
        conn = get_db()
        with conn:
            contact = conn.execute('SELECT phone FROM contact_info WHERE id = 1').fetchone()
        return contact
    finally:
        conn.close()

def update_contact_info(phone):
    try:
        conn = get_db()
        with conn:
            conn.execute('UPDATE contact_info SET phone = ? WHERE id = 1', (phone,))
    finally:
        conn.close()

def get_help_content():
    try:
        conn = get_db()
        with conn:
            help_content = conn.execute('SELECT content FROM help_content WHERE id = 1').fetchone()
        return help_content
    finally:
        conn.close()

def update_help_content(content):
    try:
        conn = get_db()
        with conn:
            conn.execute('UPDATE help_content SET content = ? WHERE id = 1', (content,))
    finally:
        conn.close()

def get_all_users():
    try:
        conn = get_db()
        with conn:
            users = conn.execute('SELECT id, student_id, name, class_name, batch, is_admin FROM users ORDER BY id').fetchall()
        return users
    finally:
        conn.close()

def add_user(student_id, name, password, class_name, batch, is_admin):
    try:
        conn = get_db()
        with conn:
            hashed_password = generate_password_hash(password)
            conn.execute('''
                INSERT INTO users (student_id, name, password, class_name, batch, is_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, name, hashed_password, class_name, batch, is_admin))
            user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.execute('''
                INSERT INTO transfer_status (user_id, transfer_status, receive_status, progress)
                VALUES (?, ?, ?, ?)
            ''', (user_id, '未开始', '未开始', 0))
        return user_id
    finally:
        conn.close()

def update_user(user_id, student_id, name, class_name, batch, is_admin, password=None):
    try:
        conn = get_db()
        with conn:
            if password:
                hashed_password = generate_password_hash(password)
                conn.execute('''
                    UPDATE users
                    SET student_id = ?, name = ?, password = ?, class_name = ?, batch = ?, is_admin = ?
                    WHERE id = ?
                ''', (student_id, name, hashed_password, class_name, batch, is_admin, user_id))
            else:
                conn.execute('''
                    UPDATE users
                    SET student_id = ?, name = ?, class_name = ?, batch = ?, is_admin = ?
                    WHERE id = ?
                ''', (student_id, name, class_name, batch, is_admin, user_id))
    finally:
        conn.close()

def delete_user(user_id):
    try:
        conn = get_db()
        with conn:
            conn.execute('DELETE FROM user_identities WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM user_materials WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM transfer_status WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM signatures WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM user_cultivators WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    finally:
        conn.close()

def reset_user_data(user_id=None):
    try:
        conn = get_db()
        with conn:
            if user_id:
                # 重置单个用户的材料状态
                conn.execute('''
                    UPDATE user_materials
                    SET status = '待审核', details = ''
                    WHERE user_id = ?
                ''', (user_id,))
                # 重置单个用户的转接状态
                conn.execute('''
                    UPDATE transfer_status
                    SET transfer_status = '未开始', receive_status = '未开始', progress = 0, abandoned_at = NULL
                    WHERE user_id = ?
                ''', (user_id,))
                # 删除单个用户的签名
                conn.execute('DELETE FROM signatures WHERE user_id = ?', (user_id,))
            else:
                # 重置所有用户的材料状态
                conn.execute('''
                    UPDATE user_materials
                    SET status = '待审核', details = ''
                ''')
                # 重置所有用户的转接状态
                conn.execute('''
                    UPDATE transfer_status
                    SET transfer_status = '未开始', receive_status = '未开始', progress = 0, abandoned_at = NULL
                ''')
                # 删除所有签名
                conn.execute('DELETE FROM signatures')
    finally:
        conn.close()

def get_dashboard_metrics():
    try:
        conn = get_db()
        with conn:
            metrics = {
                'total_users': conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 0').fetchone()[0],
                'transfer_statuses': conn.execute('''
                    SELECT transfer_status, COUNT(*) as count
                    FROM transfer_status
                    GROUP BY transfer_status
                ''').fetchall(),
                'material_completeness': conn.execute('''
                    SELECT AVG(
                        (SELECT COUNT(*) FROM user_materials um WHERE um.user_id = u.id AND um.status = '齐全') * 100.0 /
                        (SELECT COUNT(*) FROM user_materials um WHERE um.user_id = u.id)
                    ) as avg_completeness
                    FROM users u
                    WHERE is_admin = 0
                ''').fetchone()[0] or 0
            }
        return metrics
    finally:
        conn.close()

def get_material_checklist():
    try:
        conn = get_db()
        with conn:
            # 获取所有用户及其身份信息
            users = conn.execute('''
                SELECT u.id, u.student_id, u.name, u.batch, 
                       GROUP_CONCAT(i.id) as identity_ids,
                       GROUP_CONCAT(i.name) as identity_names
                FROM users u
                LEFT JOIN user_identities ui ON u.id = ui.user_id
                LEFT JOIN identities i ON ui.identity_id = i.id
                WHERE u.is_admin = 0
                GROUP BY u.id
                ORDER BY u.id
            ''').fetchall()
            
            # 转换identity_ids和identity_names为列表
            users = [dict(user) for user in users]
            for user in users:
                user['identity_ids'] = [int(i) for i in (user['identity_ids'].split(',') if user['identity_ids'] else [])]
                user['identity_names'] = user['identity_names'].split(',') if user['identity_names'] else []
            
            # 获取所有材料和身份
            materials = conn.execute('''
                SELECT m.id, m.name, 
                       GROUP_CONCAT(mi.identity_id) as identity_ids
                FROM materials m
                LEFT JOIN identity_materials mi ON m.id = mi.material_id
                GROUP BY m.id
                ORDER BY m.id
            ''').fetchall()
            materials = [dict(m) for m in materials]
            for m in materials:
                m['identity_ids'] = [int(i) for i in (m['identity_ids'].split(',') if m['identity_ids'] else [])]
            
            identities = conn.execute('SELECT id, name FROM identities ORDER BY id').fetchall()
            
            checklist = []
            for user in users:
                user_materials = conn.execute('''
                    SELECT m.id, m.name, 
                           COALESCE(um.status, '') as status,
                           COALESCE(um.details, '') as details
                    FROM materials m
                    LEFT JOIN user_materials um ON m.id = um.material_id AND um.user_id = ?
                    ORDER BY m.id
                ''', (user['id'],)).fetchall()
                user_materials = [dict(m) for m in user_materials]
                
                # 计算 completeness 状态
                complete_count = sum(1 for m in user_materials if m['status'] == '齐全')
                pending_count = sum(1 for m in user_materials if m['status'] == '待审核')
                total_count = sum(1 for m in user_materials if m['status'])
                
                if total_count == 0:
                    completeness = 'incomplete'
                elif complete_count == len(user_materials):
                    completeness = 'complete'
                elif pending_count == len(user_materials):
                    completeness = 'pending'
                else:
                    completeness = 'partial'
                
                checklist.append({
                    'user': user,
                    'materials': user_materials,
                    'completeness': completeness
                })
        
        return {
            'users': users,
            'materials': materials,
            'checklist': checklist,
            'identities': identities
        }
    finally:
        conn.close()

def get_all_cultivators():
    try:
        conn = get_db()
        with conn:
            cultivators = conn.execute('SELECT id, name, role FROM cultivators ORDER BY id').fetchall()
        return cultivators
    finally:
        conn.close()

def add_cultivator(name, role):
    try:
        conn = get_db()
        with conn:
            conn.execute('INSERT INTO cultivators (name, role) VALUES (?, ?)', (name, role))
    finally:
        conn.close()

def update_cultivator(cultivator_id, name, role):
    try:
        conn = get_db()
        with conn:
            conn.execute('UPDATE cultivators SET name = ?, role = ? WHERE id = ?', (name, role, cultivator_id))
    finally:
        conn.close()

def delete_cultivator(cultivator_id):
    try:
        conn = get_db()
        with conn:
            conn.execute('DELETE FROM user_cultivators WHERE cultivator_id = ?', (cultivator_id,))
            conn.execute('DELETE FROM cultivators WHERE id = ?', (cultivator_id,))
    finally:
        conn.close()

def get_user_cultivator_ids(user_id):
    try:
        conn = get_db()
        with conn:
            cultivator_ids = conn.execute('SELECT cultivator_id FROM user_cultivators WHERE user_id = ?', (user_id,)).fetchall()
        return [c['cultivator_id'] for c in cultivator_ids]
    finally:
        conn.close()

def update_user_cultivators(user_id, cultivator_ids):
    try:
        conn = get_db()
        with conn:
            conn.execute('DELETE FROM user_cultivators WHERE user_id = ?', (user_id,))
            for cultivator_id in cultivator_ids:
                conn.execute('INSERT OR IGNORE INTO user_cultivators (user_id, cultivator_id) VALUES (?, ?)', (user_id, cultivator_id))
    finally:
        conn.close()

def log_operation(operator_id, operator_name, action, target=None, details=None):
    """记录管理员操作日志"""
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                INSERT INTO operation_logs (operator_id, operator_name, action, target, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (operator_id, operator_name, action, target, details, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    finally:
        conn.close()

def get_operation_logs(limit=50):
    """获取操作日志"""
    try:
        conn = get_db()
        with conn:
            logs = conn.execute('''
                SELECT id, operator_name, action, target, details, created_at
                FROM operation_logs
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
        return logs
    finally:
        conn.close()

def search_operation_logs(search=None, action=None, date_from=None, date_to=None, page=1, per_page=20):
    """搜索和筛选操作日志，支持分页"""
    try:
        conn = get_db()
        with conn:
            where_clauses = []
            params = []

            if search:
                where_clauses.append("(operator_name LIKE ? OR target LIKE ? OR details LIKE ?)")
                s = f"%{search}%"
                params.extend([s, s, s])

            if action:
                where_clauses.append("action = ?")
                params.append(action)

            if date_from:
                where_clauses.append("created_at >= ?")
                params.append(date_from)

            if date_to:
                where_clauses.append("created_at <= ?")
                params.append(date_to + ' 23:59:59')

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # 获取总数
            count_sql = f"SELECT COUNT(*) FROM operation_logs {where_sql}"
            total = conn.execute(count_sql, params).fetchone()[0]

            # 获取分页数据
            offset = (page - 1) * per_page
            data_sql = f'''
                SELECT id, operator_name, action, target, details, created_at
                FROM operation_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            logs = conn.execute(data_sql, params + [per_page, offset]).fetchall()

            # 获取所有操作类型
            actions = conn.execute('SELECT DISTINCT action FROM operation_logs ORDER BY action').fetchall()

        return {
            'logs': [dict(log) for log in logs],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 1,
            'actions': [a['action'] for a in actions]
        }
    finally:
        conn.close()

def ensure_operation_logs_table():
    """确保操作日志表存在"""
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_id INTEGER NOT NULL,
                    operator_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (operator_id) REFERENCES users(id)
                )
            ''')
    finally:
        conn.close()

def ensure_fee_records_table():
    """确保党费缴纳记录表存在"""
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fee_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT '未缴纳',
                    paid_date TEXT,
                    remark TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, year, month)
                )
            ''')
    finally:
        conn.close()

def get_fee_records(user_id=None, year=None, month=None, status=None, page=1, per_page=20):
    """获取党费缴纳记录，支持筛选和分页"""
    try:
        conn = get_db()
        with conn:
            where_clauses = []
            params = []

            if user_id:
                where_clauses.append("fr.user_id = ?")
                params.append(user_id)
            if year:
                where_clauses.append("fr.year = ?")
                params.append(int(year))
            if month:
                where_clauses.append("fr.month = ?")
                params.append(int(month))
            if status:
                where_clauses.append("fr.status = ?")
                params.append(status)

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            count_sql = f"SELECT COUNT(*) FROM fee_records fr {where_sql}"
            total = conn.execute(count_sql, params).fetchone()[0]

            offset = (page - 1) * per_page
            data_sql = f'''
                SELECT fr.id, fr.user_id, u.student_id, u.name, u.class_name, u.batch,
                       fr.year, fr.month, fr.amount, fr.status, fr.paid_date, fr.remark
                FROM fee_records fr
                JOIN users u ON fr.user_id = u.id
                {where_sql}
                ORDER BY fr.year DESC, fr.month DESC, u.student_id
                LIMIT ? OFFSET ?
            '''
            records = conn.execute(data_sql, params + [per_page, offset]).fetchall()

        return {
            'records': [dict(r) for r in records],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 1
        }
    finally:
        conn.close()

def get_user_fee_records(user_id, year=None):
    """获取指定用户的党费缴纳记录"""
    try:
        conn = get_db()
        with conn:
            if year:
                records = conn.execute('''
                    SELECT id, year, month, amount, status, paid_date, remark
                    FROM fee_records WHERE user_id = ? AND year = ?
                    ORDER BY year DESC, month DESC
                ''', (user_id, int(year))).fetchall()
            else:
                records = conn.execute('''
                    SELECT id, year, month, amount, status, paid_date, remark
                    FROM fee_records WHERE user_id = ?
                    ORDER BY year DESC, month DESC
                ''', (user_id,)).fetchall()
        return [dict(r) for r in records]
    finally:
        conn.close()

def add_fee_record(user_id, year, month, amount, status='未缴纳', paid_date=None, remark=None):
    """添加党费缴纳记录"""
    try:
        conn = get_db()
        with conn:
            conn.execute('''
                INSERT INTO fee_records (user_id, year, month, amount, status, paid_date, remark, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, int(year), int(month), float(amount), status, paid_date, remark,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    finally:
        conn.close()

def update_fee_record(record_id, amount=None, status=None, paid_date=None, remark=None):
    """更新党费缴纳记录"""
    try:
        conn = get_db()
        with conn:
            updates = []
            params = []
            if amount is not None:
                updates.append("amount = ?")
                params.append(float(amount))
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if paid_date is not None:
                updates.append("paid_date = ?")
                params.append(paid_date)
            if remark is not None:
                updates.append("remark = ?")
                params.append(remark)
            updates.append("updated_at = ?")
            params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            params.append(int(record_id))
            conn.execute(f"UPDATE fee_records SET {', '.join(updates)} WHERE id = ?", params)
    finally:
        conn.close()

def delete_fee_record(record_id):
    """删除党费缴纳记录"""
    try:
        conn = get_db()
        with conn:
            conn.execute('DELETE FROM fee_records WHERE id = ?', (int(record_id),))
    finally:
        conn.close()

def batch_generate_fee_records(year, months, amount):
    """批量生成党费缴纳记录（为所有非管理员用户）"""
    try:
        conn = get_db()
        with conn:
            users = conn.execute('SELECT id FROM users WHERE is_admin = 0').fetchall()
            count = 0
            for user in users:
                for month in months:
                    exists = conn.execute(
                        'SELECT 1 FROM fee_records WHERE user_id = ? AND year = ? AND month = ?',
                        (user['id'], int(year), int(month))
                    ).fetchone()
                    if not exists:
                        conn.execute('''
                            INSERT INTO fee_records (user_id, year, month, amount, status, updated_at)
                            VALUES (?, ?, ?, ?, '未缴纳', ?)
                        ''', (user['id'], int(year), int(month), float(amount),
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        count += 1
        return count
    finally:
        conn.close()

def get_fee_statistics(year=None):
    """获取党费缴纳统计"""
    try:
        conn = get_db()
        with conn:
            year_filter = "WHERE fr.year = ?" if year else ""
            params = [int(year)] if year else []

            # 按状态统计
            status_stats = conn.execute(f'''
                SELECT fr.status, COUNT(*) as count, SUM(fr.amount) as total_amount
                FROM fee_records fr
                {year_filter}
                GROUP BY fr.status
            ''', params).fetchall()

            # 按月统计
            month_stats = conn.execute(f'''
                SELECT fr.year, fr.month, 
                       SUM(CASE WHEN fr.status = '已缴纳' THEN 1 ELSE 0 END) as paid_count,
                       SUM(CASE WHEN fr.status = '未缴纳' THEN 1 ELSE 0 END) as unpaid_count,
                       COUNT(*) as total_count
                FROM fee_records fr
                {year_filter}
                GROUP BY fr.year, fr.month
                ORDER BY fr.year DESC, fr.month DESC
            ''', params).fetchall()

            # 总体统计
            total_records = conn.execute(f'''
                SELECT COUNT(*) FROM fee_records fr {year_filter}
            ''', params).fetchone()[0]

            paid_records = conn.execute(f'''
                SELECT COUNT(*) FROM fee_records fr {year_filter}{' AND' if year else 'WHERE'} fr.status = '已缴纳'
            ''', params).fetchone()[0]

        return {
            'status_stats': [dict(r) for r in status_stats],
            'month_stats': [dict(r) for r in month_stats],
            'total_records': total_records,
            'paid_records': paid_records,
            'unpaid_records': total_records - paid_records
        }
    finally:
        conn.close()
