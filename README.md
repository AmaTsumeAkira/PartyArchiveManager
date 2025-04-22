# 档案转接系统

## 项目概述
档案转接系统是一个用于管理学生档案转接流程的Web应用程序，特别针对高校学生党员发展过程中的档案管理需求设计。系统支持从共青团员到正式党员不同政治面貌学生的档案转接流程管理。

## 主要功能

### 管理员功能
- **用户管理**：添加、编辑、删除用户，设置用户政治面貌和权限
- **材料配置**：根据不同政治面貌配置所需的档案材料
- **转接状态管理**：查看和更新用户的档案转接状态
- **材料核对**：检查用户材料完整性，更新材料状态
- **数据初始化**：重置用户材料和转接状态
- **培养人管理**：管理学生的培养联系人信息
- **系统公告**：发布和管理系统公告

### 学生功能
- **档案状态查询**：查看个人档案转接进度和材料完整性
- **材料提交**：查看和补全所需材料
- **转接申请**：提交档案转接申请
- **放弃转接**：自愿放弃积极分子身份的签名确认流程

## 系统特点
- 根据不同政治面貌自动计算所需材料
- 高等级身份自动继承低等级身份的所有材料
- 实时计算材料完整度百分比
- 支持电子签名确认放弃转接操作
- 详细的转接进度跟踪

## 技术栈
- **后端**：Python Flask框架
- **数据库**：SQLite
- **前端**：HTML, CSS, JavaScript, Jinja2模板
- **依赖**：
  - Flask==2.3.3
  - Werkzeug==2.3.7

## 数据库结构
系统使用SQLite数据库，包含以下主要表：
- 用户表(users)
- 政治面貌表(identities)
- 材料表(materials)
- 转接状态表(transfer_status)
- 签名表(signatures)
- 培养人表(cultivators)等

## 开发环境配置

### 使用Python虚拟环境(venv)
1. 创建虚拟环境：
   ```bash
   python -m venv venv
   ```

2. 激活虚拟环境：
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. 在虚拟环境中安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 退出虚拟环境：
   ```bash
   deactivate
   ```

## 安装与运行
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 初始化数据库：
   ```bash
   python init_db.py
   ```
3. 启动应用：
   ```bash
   python app.py
   ```
4. 访问系统：
   - 管理员：http://localhost:8888/admin
   - 学生：http://localhost:8888

## 默认账号
- 管理员账号：admin / sxcz123456
- 学生账号：
  - 2025210101 / sxcz123456
  - 2025210102 / sxcz123456

## 项目结构
```
archive-system/
├── app.py                # 主应用程序
├── database.py           # 数据库操作
├── init_db.py            # 数据库初始化
├── requirements.txt      # 依赖文件
├── templates/            # 前端模板
│   ├── admin.html        # 管理员仪表盘
│   ├── admin_users.html  # 用户管理
│   ├── login.html        # 登录页面
│   └── ...               # 其他模板文件
└── static/               # 静态资源
```
