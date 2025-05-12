from app import app, db
from app import Class, Subject, Teacher, Student

with app.app_context():
    # Очистка и создание таблиц
    db.drop_all()
    db.create_all()

    # Добавление тестовых данных
    # Сначала создаём классы
    classes = [
        Class(name='5А'),
        Class(name='5Б'),
        Class(name='6А'),
        Class(name='6Б'),
        Class(name='7А'),
        Class(name='7Б')
    ]

    # Добавляем классы в сессию и сохраняем их в базе данных
    db.session.add_all(classes)
    db.session.commit()

    # Создаём предметы
    subjects = [
        Subject(name='Математика'),
        Subject(name='Русский язык')
    ]

    # Создаём учителя
    teacher = Teacher(username='teacher1', password='password123', full_name='Иванов Иван Иванович')

    # Добавляем учеников в классы
    students = [
        Student(full_name='Иванов Иван', class_id=classes[0].id),  # 5А
        Student(full_name='Петров Петр', class_id=classes[0].id),  # 5А
        Student(full_name='Сидоров Сидор', class_id=classes[1].id),  # 5Б
        Student(full_name='Алексеев Алексей', class_id=classes[1].id),  # 5Б
        Student(full_name='Смирнов Сергей', class_id=classes[2].id),  # 6А
        Student(full_name='Козлов Кирилл', class_id=classes[2].id),  # 6А
        Student(full_name='Морозов Максим', class_id=classes[3].id),  # 6Б
        Student(full_name='Васильев Виктор', class_id=classes[3].id),  # 6Б
        Student(full_name='Егоров Евгений', class_id=classes[4].id),  # 7А
        Student(full_name='Фёдоров Фёдор', class_id=classes[4].id),  # 7А
        Student(full_name='Николаев Николай', class_id=classes[5].id),  # 7Б
        Student(full_name='Дмитриев Дмитрий', class_id=classes[5].id)  # 7Б
    ]

    # Добавляем всё в сессию
    db.session.add_all(subjects)
    db.session.add(teacher)
    db.session.add_all(students)
    db.session.commit()

    print("Тестовые данные успешно добавлены!")