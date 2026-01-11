from app import app

if __name__ == '__main__':
    print("\nAvailable Routes:")
    for rule in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        methods = ','.join(method for method in rule.methods if method != 'HEAD' and method != 'OPTIONS')
        print(f"{rule} [{methods}]") 