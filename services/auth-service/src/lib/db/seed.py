import os
import sys
import datetime

# Add the project root to sys.path to allow absolute imports of 'src'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Remove script's own folder to prevent importing 'peewee.py' instead of library 'peewee'
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)


from src.entities.user import User, UserPlan, UserRole
from src.services.auth_service import hash_password
from src.lib.db.peewee import init_db

def seed_db():
    print("Connecting and initializing database...")
    db = init_db()
    
    # ── Test accounts data ────────────────────────────────────────────────────
    seed_users = [
        {
            "email": "free@veritas.ai",
            "password": "password123",
            "full_name": "Free Account",
            "role": UserRole.USER.value,
            "plan": UserPlan.FREE.value,
            "stripe_subscription_status": None,
        },
        {
            "email": "pro@veritas.ai",
            "password": "password123",
            "full_name": "Pro Account",
            "role": UserRole.USER.value,
            "plan": UserPlan.PRO.value,
            "stripe_customer_id": "cus_seeded_pro",
            "stripe_subscription_id": "sub_seeded_pro",
            "stripe_subscription_status": "active",
        },
        {
            "email": "enterprise@veritas.ai",
            "password": "password123",
            "full_name": "Enterprise Account",
            "role": UserRole.USER.value,
            "plan": UserPlan.ENTERPRISE.value,
            "stripe_customer_id": "cus_seeded_ent",
            "stripe_subscription_id": "sub_seeded_ent",
            "stripe_subscription_status": "active",
        },
        {
            "email": "admin@veritas.ai",
            "password": "password123",
            "full_name": "Veritas Admin",
            "role": UserRole.ADMIN.value,
            "plan": UserPlan.ENTERPRISE.value,
            "stripe_subscription_status": None,
        }
    ]
    
    # ── Database write operations ──────────────────────────────────────────────
    for u_data in seed_users:
        user = User.get_or_none(User.email == u_data["email"])
        if not user:
            print(f"Creating test account: {u_data['email']} ({u_data['plan']})")
            User.create(
                email=u_data["email"],
                password_hash=hash_password(u_data["password"]),
                full_name=u_data["full_name"],
                role=u_data["role"],
                plan=u_data["plan"],
                stripe_customer_id=u_data.get("stripe_customer_id"),
                stripe_subscription_id=u_data.get("stripe_subscription_id"),
                stripe_subscription_status=u_data.get("stripe_subscription_status"),
                is_verified=True
            )
        else:
            print(f"Account exists: {u_data['email']}. Reseeding settings and plan to '{u_data['plan']}'")
            user.plan = u_data["plan"]
            user.role = u_data["role"]
            user.stripe_customer_id = u_data.get("stripe_customer_id") or user.stripe_customer_id
            user.stripe_subscription_id = u_data.get("stripe_subscription_id") or user.stripe_subscription_id
            user.stripe_subscription_status = u_data.get("stripe_subscription_status") or user.stripe_subscription_status
            user.save()
            
    print("Database seeding successfully completed!")

if __name__ == "__main__":
    seed_db()
