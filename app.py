from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schoolroom.db'
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
    attendance_records = {}  # Словарь для хранения существующих записей

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

            # Получаем существующие записи посещаемости для выбранной даты, класса и предмета
            for student in students:
                attendance_record = Attendance.query.filter_by(
                    student_id=student.id,
                    subject_id=subject_id,
                    date=date
                ).first()
                attendance_records[student.id] = attendance_record

            if 'submit_attendance' in request.form:
                for student in students:
                    # Чекбокс передаётся в форме только если он отмечен, иначе его нет в request.form
                    present = f'present_{student.id}' in request.form
                    print(f"Student {student.full_name} (ID: {student.id}), Present: {present}")  # Отладка

                    attendance_record = Attendance.query.filter_by(
                        student_id=student.id,
                        subject_id=subject_id,
                        date=date
                    ).first()

                    if attendance_record:
                        # Если запись существует, обновляем её
                        attendance_record.present = present
                        print(f"Updated attendance for {student.full_name}: Present = {present}")
                    else:
                        # Если записи нет, создаём новую
                        new_attendance = Attendance(
                            date=date,
                            present=present,
                            student_id=student.id,
                            subject_id=subject_id
                        )
                        db.session.add(new_attendance)
                        print(f"Added new attendance for {student.full_name}: Present = {present}")

                # Фиксируем изменения в базе данных
                db.session.commit()

                # Проверяем, что данные действительно сохранены
                saved_records = Attendance.query.filter_by(subject_id=subject_id, date=date).all()
                print(f"Saved attendance records: {[(rec.student_id, rec.present) for rec in saved_records]}")

                flash('Посещаемость успешно сохранена.', 'success')
                return redirect(url_for('attendance'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
            print(f"Error: {str(e)}")  # Отладка

    return render_template(
        'attendance.html',
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subject=selected_subject,
        selected_date=selected_date,
        students=students,
        attendance_records=attendance_records
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
    grade_records = {}  # Словарь для хранения существующих оценок

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

            # Получаем существующие оценки для выбранной даты, класса и предмета
            for student in students:
                grade_record = Grade.query.filter_by(
                    student_id=student.id,
                    subject_id=subject_id,
                    date=date
                ).first()
                grade_records[student.id] = grade_record

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
        students=students,
        grade_records=grade_records  # Передаём существующие оценки
    )

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    classes = Class.query.all()
    subjects = Subject.query.all()
    selected_class = None
    selected_subject = None
    student_data = []

    if request.method == 'POST':
        try:
            class_id = request.form.get('class_id')
            subject_id = request.form.get('subject_id')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')

            if not class_id or not subject_id or not start_date or not end_date:
                flash('Пожалуйста, выберите класс, предмет и диапазон дат.', 'danger')
                return redirect(url_for('reports'))

            selected_class = Class.query.get_or_404(class_id)
            selected_subject = Subject.query.get_or_404(subject_id)
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            students = sorted(selected_class.students, key=lambda student: student.full_name)

            # Собираем данные для отчёта с фильтром по датам
            for student in students:
                # Посещаемость
                attendance_records = Attendance.query.filter(
                    Attendance.student_id == student.id,
                    Attendance.subject_id == subject_id,
                    Attendance.date >= start_date,
                    Attendance.date <= end_date
                ).all()
                total_days = len(attendance_records)
                present_days = sum(1 for record in attendance_records if record.present)  # Подсчитываем дни с present=True
                attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0

                # Отладочный вывод
                print(f"Student: {student.full_name}, Total Days: {total_days}, Present Days: {present_days}, Percentage: {attendance_percentage}%")

                # Оценки
                grades = Grade.query.filter(
                    Grade.student_id == student.id,
                    Grade.subject_id == subject_id,
                    Grade.date >= start_date,
                    Grade.date <= end_date
                ).all()
                grade_values = [grade.value for grade in grades]
                average_grade = sum(grade_values) / len(grade_values) if grade_values else None

                # Формируем данные для отображения
                student_data.append({
                    'full_name': student.full_name,
                    'attendance_percentage': round(attendance_percentage, 2),
                    'grades': grade_values,
                    'average_grade': round(average_grade, 2) if average_grade else None,
                    'total_days': total_days,  # Для отладки
                    'present_days': present_days  # Для отладки
                })

            # Экспорт в PDF, если запрошено
            if 'export_pdf' in request.form:
                output = io.BytesIO()
                doc = SimpleDocTemplate(output, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []

                # Регистрация шрифта с поддержкой кириллицы
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))  # Убедитесь, что шрифт доступен

                # Изменяем стиль для поддержки кириллицы
                styles['Title'].fontName = 'DejaVuSans'
                styles['Normal'].fontName = 'DejaVuSans'

                title = Paragraph(f"Отчёт по классу {selected_class.name} ({selected_subject.name}) с {start_date} по {end_date}", styles['Title'])
                elements.append(title)

                table_data = [['ФИО', 'Посещаемость (%)', 'Оценки', 'Средняя оценка']]
                for student in student_data:
                    table_data.append([
                        student['full_name'],
                        f"{student['attendance_percentage']}%",
                        ', '.join(map(str, student['grades'])) if student['grades'] else 'Нет оценок',
                        str(student['average_grade']) if student['average_grade'] else 'Нет оценок'
                    ])

                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),  # Используем шрифт с кириллицей
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)

                doc.build(elements)
                output.seek(0)
                return send_file(output, as_attachment=True, download_name=f"report_{selected_class.name}_{selected_subject.name}.pdf", mimetype='application/pdf')

        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'error')

    return render_template(
        'reports.html',
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subject=selected_subject,
        student_data=student_data if student_data else None,
        start_date=start_date.strftime('%Y-%m-%d') if 'start_date' in locals() else '',
        end_date=end_date.strftime('%Y-%m-%d') if 'end_date' in locals() else ''
    )

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