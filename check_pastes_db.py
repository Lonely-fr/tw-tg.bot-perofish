#!/usr/bin/env python3
import sqlite3

def main():
    # Connect to the database
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # Check for pastes tables
    tables_to_check = ['pastes', 'pastes_votes', 'pastes_suggestions']
    
    print("Checking pastes-related tables:")
    for table in tables_to_check:
        try:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            if columns:
                print(f"\nTable: {table}")
                for column in columns:
                    print(f"  {column[1]} ({column[2]})")
            else:
                print(f"\nTable {table} not found")
        except Exception as e:
            print(f"Error checking table {table}: {e}")
    
    # Check sample data
    print("\n\nSample data from pastes table:")
    try:
        cursor.execute("SELECT id, name, text FROM pastes LIMIT 5;")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, Text: {row[2][:50]}...")
    except Exception as e:
        print(f"Error retrieving sample data: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()