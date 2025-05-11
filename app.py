from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///webflask.db'
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
db = SQLAlchemy(app)

# Модели
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    students = db.relationship('Student', backref='class', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    attendances = db.relationship('Attendance', backref='student', lazy=True, cascade="all, delete-orphan")
    grades = db.relationship('Grade', backref='student', lazy=True, cascade="all, delete-orphan")

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    present = db.Column(db.Boolean, default=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))

# Функция для проверки авторизации
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Пожалуйста, войдите в систему.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Очистка сессии при каждом запросе к главной странице
@app.before_request
def clear_session_on_index():
    if request.endpoint == 'index':
        session.clear()

# Маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        teacher = Teacher.query.filter_by(username=username, password=password).first()
        if teacher:
            session['teacher_id'] = teacher.id
            flash('Вход успешен!', 'success')
            return redirect(url_for('class_list'))
        else:
            flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        if Teacher.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует.', 'danger')
        else:
            new_teacher = Teacher(username=username, password=password, full_name=full_name)
            db.session.add(new_teacher)
            db.session.commit()
            session['teacher_id'] = new_teacher.id
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('class_list'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('index'))

@app.route('/classes')
@login_required
def class_list():
    classes = Class.query.all()
    return render_template('classes.html', classes=classes)

@app.route('/class/<int:class_id>')
@login_required
def class_detail(class_id):
    class_ = Class.query.get_or_404(class_id)
    students = sorted(class_.students, key=lambda student: student.full_name)
    return render_template('class_detail.html', class_=class_, students=students)

@app.route('/student/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        try:
            full_name = request.form['full_name']
            class_id = request.form['class_id']
            new_student = Student(
                full_name=full_name,
                class_id=class_id
            )
            db.session.add(new_student)
            db.session.commit()
            flash('Ученик успешно добавлен', 'success')
            return redirect(url_for('class_detail', class_id=class_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
    classes = Class.query.all()
    return render_template('student_form.html', classes=classes)

@app.route('/student/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    class_id = student.class_id
    try:
        db.session.delete(student)
        db.session.commit()
        flash('Ученик успешно удалён', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'error')
    return redirect(url_for('class_detail', class_id=class_id))

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    classes = Class.query.all()
    subjects = Subject.query.all()
    selected_class = None
    selected_subject = None
    selected_date = None
    students = []

    if request.method == 'POST':
        try:
            class_id = request.form.get('class_id')
            subject_id = request.form.get('subject_id')
            selected_date = request.form.get('date')

            if not class_id or not subject_id or not selected_date:
                flash('Пожалуйста, выберите класс, предмет и дату.', 'danger')
                return redirect(url_for('attendance'))

            date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            selected_class = Class.query.get_or_404(class_id)
            selected_subject = Subject.query.get_or_404(subject_id)
            students = sorted(selected_class.students, key=lambda student: student.full_name)

            if 'submit_attendance' in request.form:
                for student in students:
                    present = f'present_{student.id}' in request.form
                    attendance_record = Attendance.query.filter_by(
                        student_id=student.id,
                        subject_id=subject_id,
                        date=date
                    ).first()

                    if attendance_record:
                        attendance_record.present = present
                    else:
                        new_attendance = Attendance(
                            date=date,
                            present=present,
                            student_id=student.id,
                            subject_id=subject_id
                        )
                        db.session.add(new_attendance)

                db.session.commit()
                flash('Посещаемость успешно сохранена.', 'success')
                return redirect(url_for('attendance'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

    return render_template(
        'attendance.html',
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subject=selected_subject,
        selected_date=selected_date,
        students=students
    )

@app.route('/grades', methods=['GET', 'POST'])
@login_required
def grades():
    classes = Class.query.all()
    subjects = Subject.query.all()
    selected_class = None
    selected_subject = None
    selected_date = None
    students = []

    if request.method == 'POST':
        try:
            class_id = request.form.get('class_id')
            subject_id = request.form.get('subject_id')
            selected_date = request.form.get('date')

            if not class_id or not subject_id or not selected_date:
                flash('Пожалуйста, выберите класс, предмет и дату.', 'danger')
                return redirect(url_for('grades'))

            date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            selected_class = Class.query.get_or_404(class_id)
            selected_subject = Subject.query.get_or_404(subject_id)
            students = sorted(selected_class.students, key=lambda student: student.full_name)

            if 'submit_grades' in request.form:
                for student in students:
                    grade_value = request.form.get(f'grade_{student.id}')
                    if grade_value and grade_value.isdigit():  # Проверяем, что оценка выбрана
                        grade_value = int(grade_value)
                        # Проверяем, есть ли уже оценка для этого ученика, предмета и даты
                        grade_record = Grade.query.filter_by(
                            student_id=student.id,
                            subject_id=subject_id,
                            date=date
                        ).first()

                        if grade_record:
                            # Если оценка уже существует, обновляем её
                            grade_record.value = grade_value
                        else:
                            # Если оценки нет, создаём новую
                            new_grade = Grade(
                                value=grade_value,
                                date=date,
                                student_id=student.id,
                                subject_id=subject_id
                            )
                            db.session.add(new_grade)

                db.session.commit()
                flash('Оценки успешно сохранены.', 'success')
                return redirect(url_for('grades'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

    return render_template(
        'grades.html',
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subject=selected_subject,
        selected_date=selected_date,
        students=students
    )

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/forecast')
@login_required
def forecast():
    return render_template('forecast.html')

@app.route('/class/add', methods=['GET', 'POST'])
@login_required
def add_class():
    if request.method == 'POST':
        try:
            name = request.form['name']
            if Class.query.filter_by(name=name).first():
                flash('Класс с таким названием уже существует.', 'danger')
            else:
                new_class = Class(name=name)
                db.session.add(new_class)
                db.session.commit()
                flash('Класс успешно добавлен.', 'success')
                return redirect(url_for('class_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
    return render_template('class_form.html')



# Инициализация базы данных
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)