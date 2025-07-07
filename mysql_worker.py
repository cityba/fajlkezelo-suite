import sys
import os
import json
import mysql.connector
from mysql.connector import errorcode

def run_command(settings, command, *args):
    try:
        conn = mysql.connector.connect(
            host=settings['server'],
            user=settings['user'],
            password=settings['password'],
            database=settings['database']
        )
        cursor = conn.cursor()
        
        result = {}
        
        if command == 'connect':
            # Csak a kapcsolat tesztelése
            result['status'] = 'success'
            result['message'] = 'Sikeres kapcsolódás'
        
        elif command == 'get_tables':
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            result['tables'] = tables
        
        elif command == 'get_table_data':
            table_name = args[0]
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 500")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            # Konvertáljuk az adatokat JSON-kompatibilis formátumba
            converted_rows = []
            for row in rows:
                converted_row = []
                for value in row:
                    if value is None:
                        converted_row.append(None)
                    elif isinstance(value, (bytes, bytearray)):
                        converted_row.append("<BINÁRIS ADAT>")
                    else:
                        converted_row.append(str(value))
                converted_rows.append(converted_row)
            
            result['columns'] = columns
            result['rows'] = converted_rows
        
        elif command == 'execute_query':
            query = args[0]
            cursor.execute(query)
            if query.strip().lower().startswith('select'):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                converted_rows = []
                for row in rows:
                    converted_row = []
                    for value in row:
                        if value is None:
                            converted_row.append(None)
                        elif isinstance(value, (bytes, bytearray)):
                            converted_row.append("<BINÁRIS ADAT>")
                        else:
                            converted_row.append(str(value))
                    converted_rows.append(converted_row)
                
                result['columns'] = columns
                result['rows'] = converted_rows
            else:
                conn.commit()
                result['rowcount'] = cursor.rowcount
                result['status'] = 'success'
        
        elif command == 'delete_row':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            query = f"DELETE FROM `{table_name}` WHERE `{pk_col}` = %s"
            cursor.execute(query, (pk_value,))
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'update_cell':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            col_name = args[3]
            new_value = args[4]
            query = f"UPDATE `{table_name}` SET `{col_name}` = %s WHERE `{pk_col}` = %s"
            cursor.execute(query, (new_value, pk_value))
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'update_record':
            table_name = args[0]
            pk_col = args[1]
            pk_value = args[2]
            updates = args[3]
            
            set_parts = []
            params = []
            for col_name, new_value in updates.items():
                set_parts.append(f"`{col_name}` = %s")
                params.append(new_value)
            params.append(pk_value)
            
            query = f"UPDATE `{table_name}` SET {', '.join(set_parts)} WHERE `{pk_col}` = %s"
            cursor.execute(query, params)
            conn.commit()
            result['rowcount'] = cursor.rowcount
            result['status'] = 'success'
        
        elif command == 'drop_table':
            table_name = args[0]
            query = f"DROP TABLE `{table_name}`"
            cursor.execute(query)
            conn.commit()
            result['status'] = 'success'
        
        cursor.close()
        conn.close()
        return result
    
    except mysql.connector.Error as err:
        return {
            'status': 'error',
            'error_code': err.errno,
            'error_message': err.msg
        }
    except Exception as e:
        return {
            'status': 'error',
            'error_message': str(e)
        }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Hibás argumentumok")
        sys.exit(1)

    arg1 = sys.argv[1]
    if os.path.isfile(arg1):
        with open(arg1, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        settings = json.loads(arg1)
 

    command = sys.argv[2]
    args = sys.argv[3:]

    result = run_command(settings, command, *args)
    print(json.dumps(result))

