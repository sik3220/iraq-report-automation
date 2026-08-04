import sqlite3

conn = sqlite3.connect("data/articles.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM articles")

articles = cursor.fetchall()

for article in articles:
    print(article)

conn.close()