import os
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from flask_cors import cross_origin

# Import domain entities
from domain.dto.UserDto import User
from domain.interfaces.dataprovider.DatabaseConfig import db

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/administracao')

def admin_login_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
def admin_redirect():
    """Redirect to admin login"""
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = os.getenv('ADMIN_USER', 'admin')
        admin_pass = os.getenv('ADMIN_PASS', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Credenciais inválidas!', 'error')
    
    return render_template('admin/admin_login.html')

@admin_bp.route('/logout')
@admin_login_required
def admin_logout():
    """Admin logout"""
    # Clear only admin session data
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/dashboard')
@admin_login_required
def admin_dashboard():
    """Admin dashboard with user management"""
    try:
        users = User.query.all()
        return render_template('admin/admin_dashboard.html', users=users)
    except Exception as e:
        flash(f'Erro ao carregar usuários: {str(e)}', 'error')
        return render_template('admin/admin_dashboard.html', users=[])

@admin_bp.route('/users/create', methods=['POST'])
@admin_login_required
def create_user():
    """Create new user"""
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('Todos os campos são obrigatórios!', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username já existe!', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email já existe!', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            documents_generated=0,
            chat_messages_sent=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Usuário {username} criado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar usuário: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@admin_login_required
def edit_user(user_id):
    """Edit existing user"""
    try:
        user = User.query.get_or_404(user_id)
        
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if username and username != user.username:
            # Check if new username already exists
            existing = User.query.filter(User.username == username, User.id != user_id).first()
            if existing:
                flash('Username já existe!', 'error')
                return redirect(url_for('admin.admin_dashboard'))
            user.username = username
        
        if email and email != user.email:
            # Check if new email already exists
            existing = User.query.filter(User.email == email, User.id != user_id).first()
            if existing:
                flash('Email já existe!', 'error')
                return redirect(url_for('admin.admin_dashboard'))
            user.email = email
        
        if password:
            user.password_hash = generate_password_hash(password)
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash(f'Usuário {user.username} atualizado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar usuário: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/users/<int:user_id>/reset', methods=['POST'])
@admin_login_required
def reset_user_counters(user_id):
    """Reset user demo counters - reset documents_generated field to zero"""
    try:
        user = User.query.get_or_404(user_id)
        user.documents_generated = 0
        user.chat_messages_sent = 0  # Also reset chat messages as per original functionality
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash(f'Contadores do usuário {user.username} resetados com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao resetar contadores: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_login_required
def delete_user(user_id):
    """Delete user"""
    try:
        user = User.query.get_or_404(user_id)
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Usuário {username} removido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover usuário: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_dashboard'))