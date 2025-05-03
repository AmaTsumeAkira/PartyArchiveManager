from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
from database import (
    get_db, get_user_by_student_id, get_user_identities, get_user_materials,
    get_transfer_status, initialize_user_materials, update_transfer_status, save_signature, get_abandoned_users,
    update_material_status, get_material_requirements, update_material_requirements,
    get_announcement, update_announcement, get_contact_info, update_contact_info,
    get_help_content, update_help_content, get_all_users, add_user, update_user,
    delete_user, get_dashboard_metrics, add_or_update_user_material,
    get_user_signature, get_user_cultivators, get_all_cultivators, add_cultivator,
    update_cultivator, delete_cultivator, get_user_cultivator_ids, update_user_cultivators,
    clean_unused_materials, delete_material, get_all_identities, update_user_identities,
    reset_user_data, get_user_identity_ids
)
import json
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

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Replace with a secure key in production

# Define add_role filter
def add_role_filter(value, cultivators):
    """
    Jinja2 filter to format cultivator name with role, e.g., '李四（教师）'.
    """
    for cultivator in cultivators:
        if cultivator['name'] == value:
            return f"{value}（{cultivator['role']}）"
    return value

# Register the filter with Jinja2
app.jinja_env.filters['add_role'] = add_role_filter

# Middleware to check if user is logged in
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Middleware to check if user is admin
def admin_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session or session.get('is_admin') != 1:
            flash('无权限访问', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('transfer'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        user = get_user_by_student_id(student_id)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['student_id'] = user['student_id']
            session['is_admin'] = user['is_admin']
            logger.debug(f"User logged in: student_id={student_id}, user_id={user['id']}, is_admin={user['is_admin']}")
            if user['is_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('transfer_popup'))
        flash('学号或密码错误', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('login'))

@app.route('/help')
@login_required
def help():
    help_content = get_help_content()
    return render_template('help.html', help_content=help_content)

@app.route('/transfer_popup')
@login_required
def transfer_popup():
    user_id = session['user_id']
    logger.debug(f"Rendering transfer_popup.html for user_id={user_id}")
    identities = get_user_identities(user_id)
    has_activist = any(identity['identity_name'] == '入党积极分子' for identity in identities)
    if not has_activist:
        return redirect(url_for('transfer'))
    return render_template('transfer_popup.html')

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    user_id = session['user_id']
    logger.debug(f"Transfer route accessed for user_id={user_id}")
    
    # 确保用户材料记录完整
    initialize_user_materials(user_id)
    
    # 获取用户学号
    conn = get_db()
    student_id = conn.execute('SELECT student_id FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if not student_id:
        logger.error(f"No user found for user_id={user_id}")
        flash('用户不存在', 'error')
        return redirect(url_for('logout'))
    student_id = student_id['student_id']
    
    # 获取用户信息、身份、材料、转接状态、签名和培养人
    user = get_user_by_student_id(student_id)
    identities = get_user_identities(user_id)
    materials = get_user_materials(user_id)
    logger.debug(f"Materials for user_id={user_id}: {[(m['id'], m['name'], m['status'], m['details']) for m in materials]}")
    transfer_status = get_transfer_status(user_id)
    signature = get_user_signature(user_id)
    cultivators = get_user_cultivators(user_id)
    
    # 获取每种身份所需的材料
    material_requirements = {
        identity['id']: get_material_requirements(identity['id'])
        for identity in identities
    }
    logger.debug(f"Material requirements: {material_requirements}")
    
    # 处理 POST 请求（放弃转接）
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'abandon':
            has_activist = any(identity['identity_name'] == '入党积极分子' for identity in identities)
            if not has_activist:
                flash('您无权放弃转接', 'error')
                return redirect(url_for('transfer'))
            return redirect(url_for('signature'))
    
    # 计算资料完整度
    required_material_ids = set()
    for identity in identities:
        for material in material_requirements[identity['id']]:
            required_material_ids.add(material['id'])
    total_materials = len(required_material_ids)
    complete_materials = sum(1 for m in materials if m['status'] == '齐全' and m['id'] in required_material_ids)
    completeness = (complete_materials / total_materials * 100) if total_materials > 0 else 0
    logger.debug(f"Completeness for user_id={user_id}: {complete_materials}/{total_materials} = {completeness:.1f}%")
    
    # 获取公告
    announcement = get_announcement()
    
    # 渲染 transfer.html 模板
    return render_template('transfer.html', 
                         identities=identities, 
                         materials=materials, 
                         transfer_status=transfer_status, 
                         completeness=completeness,
                         announcement=announcement,
                         current_user=user,
                         material_requirements=material_requirements,
                         signature=signature,
                         cultivators=cultivators)

@app.route('/signature', methods=['GET', 'POST'])
@login_required
def signature():
    user_id = session['user_id']
    identities = get_user_identities(user_id)
    has_activist = any(identity['identity_name'] == '入党积极分子' for identity in identities)
    if not has_activist:
        flash('您无权放弃转接', 'error')
        return redirect(url_for('transfer'))
    
    if request.method == 'POST':
        signature_data = request.form['signature']
        update_transfer_status(user_id, '已放弃', '已放弃', abandoned=True)
        save_signature(user_id, signature_data)
        flash('已放弃档案转接', 'success')
        return redirect(url_for('transfer'))
    
    return render_template('signature.html')

@app.route('/signature/<int:user_id>')
@login_required
def get_signature(user_id):
    if not session.get('is_admin') and session['user_id'] != user_id:
        flash('无权限查看该签字', 'error')
        return jsonify({'success': False, 'error': '无权限'}), 403
    signature = get_user_signature(user_id)
    if signature:
        logger.debug(f"Signature retrieved for user_id={user_id}")
        return jsonify({'success': True, 'signature_data': signature['signature_data'], 'created_at': signature['created_at']})
    logger.debug(f"No signature found for user_id={user_id}")
    return jsonify({'success': False, 'error': '无签字记录'})

@app.route('/admin')
@admin_required
def admin():
    metrics = get_dashboard_metrics()
    abandoned_users = get_abandoned_users()
    announcement = get_announcement()
    contact_info = get_contact_info()
    help_content = get_help_content()
    return render_template('admin.html', 
                         metrics=metrics, 
                         abandoned_users=abandoned_users,
                         announcement=announcement,
                         contact_info=contact_info,
                         help_content=help_content)

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                # 获取表单数据
                student_id = request.form['student_id']
                name = request.form['name']
                password = request.form['password']
                class_name = request.form['class_name']
                batch = request.form['batch']
                is_admin = 1 if request.form.get('is_admin') == 'on' else 0
                identity_ids = [int(i) for i in request.form.getlist('identities')]
                cultivator_ids = [int(i) for i in request.form.getlist('cultivators')]
                
                # 添加用户
                user_id = add_user(student_id, name, password, class_name, batch, is_admin)
                
                # 更新用户身份和培养人
                update_user_identities(user_id, identity_ids)
                update_user_cultivators(user_id, cultivator_ids)
                
                flash('用户添加成功', 'success')
                
            elif action == 'edit':
                # 获取表单数据
                user_id = int(request.form['user_id'])
                student_id = request.form['student_id']
                name = request.form['name']
                class_name = request.form['class_name']
                batch = request.form['batch']
                is_admin = 1 if request.form.get('is_admin') == 'on' else 0
                password = request.form.get('password')
                identity_ids = [int(i) for i in request.form.getlist('identities')]
                cultivator_ids = [int(i) for i in request.form.getlist('cultivators')]
                
                # 更新用户
                update_user(user_id, student_id, name, class_name, batch, is_admin, password)
                
                # 更新用户身份和培养人
                update_user_identities(user_id, identity_ids)
                update_user_cultivators(user_id, cultivator_ids)
                
                flash('用户更新成功', 'success')
                
            elif action == 'delete':
                user_id = int(request.form['user_id'])
                delete_user(user_id)
                flash('用户删除成功', 'success')
                
        except sqlite3.IntegrityError as e:
            flash(f'操作失败：学号可能已存在', 'error')
            logger.error(f"Database error: {str(e)}")
        except Exception as e:
            flash(f'操作失败：{str(e)}', 'error')
            logger.error(f"Unexpected error: {str(e)}")
        
        return redirect(url_for('admin_users'))
    
    # GET请求处理保持不变
    users = get_all_users()
    cultivators = get_all_cultivators()
    identities = get_all_identities()
    users_with_details = []
    
    for user in users:
        identity_ids = get_user_identity_ids(user['id'])
        identity_names = [i['identity_name'] for i in get_user_identities(user['id'])]
        cultivator_ids = get_user_cultivator_ids(user['id'])
        user_dict = dict(user)
        user_dict['identity_ids'] = identity_ids
        user_dict['identity_names'] = identity_names
        user_dict['cultivator_ids'] = cultivator_ids
        users_with_details.append(user_dict)
    
    return render_template('admin_users.html', 
                         users=users_with_details, 
                         cultivators=cultivators,
                         identities=identities)

@app.route('/apply_transfer', methods=['POST'])
@login_required
def apply_transfer():
    user_id = session['user_id']
    receiver = request.form.get('receiver')
    if not receiver:
        flash('接收地不能为空', 'error')
        return redirect(url_for('transfer'))
    try:
        update_transfer_status(user_id, '处理中', '待确认', receiver=receiver, progress=25)
        flash('转接申请提交成功', 'success')
    except Exception as e:
        logger.error(f"Error applying transfer for user_id={user_id}: {str(e)}")
        flash(f'提交失败：{str(e)}', 'error')
    return redirect(url_for('transfer'))

@app.route('/admin/update_transfer_status', methods=['POST'])
@admin_required
def admin_update_transfer_status():
    try:
        user_id = int(request.form['user_id'])
        transfer_status = request.form['transfer_status']
        receive_status = request.form['receive_status']
        progress = int(request.form['progress'])
        receiver = request.form.get('receiver', '')
        transfer_date = request.form.get('transfer_date', '')
        update_transfer_status(user_id, transfer_status, receive_status, 
                             receiver=receiver, progress=progress, transfer_date=transfer_date)
        flash('转接状态更新成功', 'success')
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating transfer status for user_id={user_id}: {str(e)}")
        flash(f'更新失败：{str(e)}', 'error')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/transfer_status')
@admin_required
def admin_transfer_status():
    try:
        conn = get_db()
        users = conn.execute('''
            SELECT u.id, u.student_id, u.name, u.class_name,
                   GROUP_CONCAT(i.name) as identity_names,
                   ts.transfer_status, ts.receive_status, ts.receiver, ts.progress, ts.transfer_date
            FROM users u
            LEFT JOIN user_identities ui ON u.id = ui.user_id
            LEFT JOIN identities i ON ui.identity_id = i.id
            LEFT JOIN transfer_status ts ON u.id = ts.user_id
            WHERE u.is_admin = 0
            GROUP BY u.id
            ORDER BY u.id
        ''').fetchall()
        # 获取所有政治面貌供筛选
        identities = conn.execute('SELECT DISTINCT name FROM identities').fetchall()
        conn.close()
        # 转换数据格式
        users = [dict(user) for user in users]
        for user in users:
            user['identity_names'] = user['identity_names'].split(',') if user['identity_names'] else []
        return render_template('admin_transfer_status.html', 
                             users=users, 
                             identities=[i['name'] for i in identities])
    except Exception as e:
        logger.error(f"Error fetching transfer statuses: {str(e)}")
        flash(f'加载失败：{str(e)}', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/reset_users', methods=['GET', 'POST'])
@admin_required
def reset_users():
    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        try:
            if not user_ids:
                flash('请至少选择一个用户进行初始化', 'error')
                return redirect(url_for('reset_users'))
            for user_id in user_ids:
                reset_user_data(user_id)
            flash(f'已成功初始化 {len(user_ids)} 个用户的数据', 'success')
        except Exception as e:
            flash(f'初始化失败：{str(e)}', 'error')
            logger.error(f"Error resetting users: {str(e)}")
        return redirect(url_for('admin_users'))
    
    users = get_all_users()
    return render_template('reset_users.html', users=users)

@app.route('/admin/materials', methods=['GET', 'POST'])
@admin_required
def admin_materials():
    if request.method == 'POST':
        try:
            identity_id = int(request.form['identity_id'])
            materials = [m.strip() for m in request.form.getlist('materials[]') if m.strip()]
            update_material_requirements(identity_id, materials)
            clean_unused_materials()
            flash('材料要求更新成功', 'success')
        except ValueError:
            flash('无效的身份ID', 'error')
            logger.error(f"Invalid identity_id: {request.form['identity_id']}")
        except Exception as e:
            flash(f'更新材料要求失败: {str(e)}', 'error')
            logger.error(f"Error updating material requirements: {str(e)}")
        return redirect(url_for('admin_materials'))
    
    identities = get_all_identities()
    material_requirements = {identity['id']: get_material_requirements(identity['id']) for identity in identities}
    return render_template('admin_materials.html', 
                         identities=identities, 
                         material_requirements=material_requirements)

@app.route('/admin/delete_material', methods=['POST'])
@admin_required
def delete_material_route():
    try:
        material_id = int(request.form['material_id'])
        identity_id = int(request.form['identity_id'])
        result = delete_material(material_id, identity_id)
        if result['success']:
            flash('材料删除成功', 'success')
            return jsonify({'success': True})
        else:
            flash(result['error'], 'error')
            return jsonify({'success': False, 'error': result['error']}), 400
    except ValueError:
        flash('无效的材料ID或身份ID', 'error')
        logger.error(f"Invalid material_id: {request.form['material_id']}, identity_id: {request.form['identity_id']}")
        return jsonify({'success': False, 'error': '无效的材料ID或身份ID'}), 400
    except Exception as e:
        flash(f'删除材料失败: {str(e)}', 'error')
        logger.error(f"Error deleting material: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/material_checklist')
@admin_required
def material_checklist():
    identities = get_all_identities()
    return render_template('admin_material_checklist.html', identities=identities)

@app.route('/admin/api/material_checklist', methods=['GET'])
@admin_required
def api_material_checklist():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '').strip()
        batch = request.args.get('batch', '').strip()
        identity_id = request.args.get('identity_id', '')
        completeness = request.args.get('completeness', 'all')

        conn = get_db()
        with conn:
            # 构建查询条件
            where_clauses = ["u.is_admin = 0"]
            params = []
            
            if search:
                where_clauses.append("(u.student_id LIKE ? OR u.name LIKE ? OR u.class_name LIKE ?)")
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])
            
            if batch:
                where_clauses.append("u.batch LIKE ?")
                params.append(f"%{batch}%")
            
            if identity_id:
                where_clauses.append("ui.identity_id = ?")
                params.append(int(identity_id))
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # 查询用户和材料状态
            query = f'''
                WITH UserMaterials AS (
                    SELECT um.user_id, m.id AS material_id, m.name AS material_name,
                           COALESCE(um.status, '') AS status,
                           COALESCE(um.details, '') AS details,
                           GROUP_CONCAT(im.identity_id) AS identity_ids
                    FROM materials m
                    LEFT JOIN user_materials um ON m.id = um.material_id
                    LEFT JOIN identity_materials im ON m.id = im.material_id
                    GROUP BY m.id, um.user_id
                ),
                UserCompleteness AS (
                    SELECT um.user_id,
                           CASE
                               WHEN COUNT(um.status) = 0 THEN 'incomplete'
                               WHEN SUM(CASE WHEN um.status = '齐全' THEN 1 ELSE 0 END) = COUNT(um.status) THEN 'complete'
                               WHEN SUM(CASE WHEN um.status = '待审核' THEN 1 ELSE 0 END) = COUNT(um.status) THEN 'pending'
                               ELSE 'partial'
                           END AS completeness
                    FROM UserMaterials um
                    GROUP BY um.user_id
                )
                SELECT u.id, u.student_id, u.name, u.batch, u.class_name,
                       GROUP_CONCAT(i.id) AS identity_ids,
                       GROUP_CONCAT(i.name) AS identity_names,
                       uc.completeness,
                       (SELECT json_group_array(
                           json_object(
                               'id', um.material_id,
                               'name', um.material_name,
                               'status', um.status,
                               'details', um.details,
                               'identity_ids', um.identity_ids
                           )
                       ) FROM UserMaterials um WHERE um.user_id = u.id) AS materials
                FROM users u
                LEFT JOIN user_identities ui ON u.id = ui.user_id
                LEFT JOIN identities i ON ui.identity_id = i.id
                LEFT JOIN UserCompleteness uc ON u.id = uc.user_id
                WHERE {where_clause}
                {'AND uc.completeness = ?' if completeness != 'all' else ''}
                GROUP BY u.id
                ORDER BY u.id
                LIMIT ? OFFSET ?
            '''
            if completeness != 'all':
                params.append(completeness)
            params.extend([per_page, (page - 1) * per_page])
            
            users = conn.execute(query, params).fetchall()
            
            # 查询总记录数
            count_query = f'''
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                LEFT JOIN user_identities ui ON u.id = ui.user_id
                WHERE {where_clause}
            '''
            count_params = params[:-2] if completeness != 'all' else params[:-2]
            total_users = conn.execute(count_query, count_params).fetchone()[0]
            
            # 获取所有材料
            materials = conn.execute('''
                SELECT m.id, m.name, GROUP_CONCAT(im.identity_id) AS identity_ids
                FROM materials m
                LEFT JOIN identity_materials im ON m.id = im.material_id
                GROUP BY m.id
                ORDER BY m.id
            ''').fetchall()

        # 格式化数据
        users_data = []
        for user in users:
            user_dict = dict(user)
            user_dict['identity_ids'] = [int(i) for i in (user['identity_ids'].split(',') if user['identity_ids'] else [])]
            user_dict['identity_names'] = user['identity_names'].split(',') if user['identity_names'] else []
            user_dict['materials'] = json.loads(user['materials'])
            for material in user_dict['materials']:
                material['identity_ids'] = [int(i) for i in (material['identity_ids'].split(',') if material['identity_ids'] else [])]
            users_data.append(user_dict)
        
        materials_data = [dict(m) for m in materials]
        for m in materials_data:
            m['identity_ids'] = [int(i) for i in (m['identity_ids'].split(',') if m['identity_ids'] else [])]
        
        return jsonify({
            'success': True,
            'users': users_data,
            'materials': materials_data,
            'identities': [dict(i) for i in get_all_identities()],
            'total_users': total_users,
            'total_pages': (total_users + per_page - 1) // per_page
        })
    except Exception as e:
        logger.error(f"Error fetching material checklist: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/update_user_material', methods=['POST'])
@admin_required
def update_user_material():
    try:
        data = request.get_json()
        user_id = data['user_id']
        updates = data['updates']
        
        conn = get_db()
        with conn:
            for update in updates:
                material_id = update['material_id']
                status = update['status']
                details = update.get('details', '')
                if not status:
                    raise ValueError(f"Invalid status for material_id={material_id}")
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
        logger.debug(f"Updated materials for user_id={user_id}: {updates}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating materials for user_id={user_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/cultivators', methods=['GET', 'POST'])
@admin_required
def admin_cultivators():
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                name = request.form['name']
                role = request.form['role']
                add_cultivator(name, role)
                flash('培养人添加成功', 'success')
            elif action == 'edit':
                cultivator_id = request.form['cultivator_id']
                name = request.form['name']
                role = request.form['role']
                update_cultivator(cultivator_id, name, role)
                flash('培养人更新成功', 'success')
            elif action == 'delete':
                cultivator_id = request.form['cultivator_id']
                delete_cultivator(cultivator_id)
                flash('培养人删除成功', 'success')
        except Exception as e:
            flash(f'操作失败：{str(e)}', 'error')
            logger.error(f"Error in cultivators: {str(e)}")
        return redirect(url_for('admin_cultivators'))
    
    cultivators = get_all_cultivators()
    return render_template('admin_cultivators.html', cultivators=cultivators)

@app.route('/admin/update_materials', methods=['POST'])
@admin_required
def update_materials():
    try:
        user_id = request.form['user_id']
        material_id = request.form['material_id']
        status = request.form['status']
        update_material_status(user_id, material_id, status)
        flash('材料状态更新成功', 'success')
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating materials: {str(e)}")
        flash('更新材料状态失败', 'error')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/update_announcement', methods=['POST'])
@admin_required
def update_announcement_route():
    try:
        content = request.form['content']
        update_date = request.form['update_date']
        update_announcement(content, update_date)
        flash('公告更新成功', 'success')
    except Exception as e:
        flash(f'公告更新失败：{str(e)}', 'error')
        logger.error(f"Error updating announcement: {str(e)}")
    return redirect(url_for('admin'))

@app.route('/admin/update_contact', methods=['POST'])
@admin_required
def update_contact():
    try:
        phone = request.form['phone']
        update_contact_info(phone)
        flash('联系电话更新成功', 'success')
    except Exception as e:
        flash(f'联系电话更新失败：{str(e)}', 'error')
        logger.error(f"Error updating contact: {str(e)}")
    return redirect(url_for('admin'))

@app.route('/admin/update_help', methods=['POST'])
@admin_required
def update_help():
    try:
        content = request.form['content']
        update_help_content(content)
        flash('帮助内容更新成功', 'success')
    except Exception as e:
        flash(f'帮助内容更新失败：{str(e)}', 'error')
        logger.error(f"Error updating help content: {str(e)}")
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8888)
