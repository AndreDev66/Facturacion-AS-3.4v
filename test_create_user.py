import db

print('Inicializando DB...')
db.init_db()

username = 'test_auto'
password = 'secret123'
print('Creando usuario:', username)
res = db.create_user(username, password)
print('Resultado create_user:', res)
print('Usuarios actuales:')
users = db.get_users()
for u in users:
    print(u)
