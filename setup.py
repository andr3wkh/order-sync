"""
Setup script - initialize database tables
"""
from models import init_db


def setup():
    """Initialize database tables"""
    
    print("Setting up Order Sync System...")
    print()
    
    print("Creating database tables...")
    init_db()
    print("✓ Tables created")
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Add stores: python manage_stores.py")
    print("2. Run system: python main.py")
    print()


if __name__ == '__main__':
    setup()
