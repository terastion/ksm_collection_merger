def log(log_type, msg):
    match log_type:
        case 'info':
            print(f'[INFO] {msg}')
        case 'log':
            print(f'[LOG] {msg}')
        case 'warn':
            print(f'[WARNING] {msg}')

def debug(debug_val, msg):
    if debug_val:
        print(f'[DEBUG] {msg}')
