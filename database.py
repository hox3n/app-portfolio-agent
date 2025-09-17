import sqlite3
import random
import math
from datetime import datetime
from pathlib import Path
from typing import List
from dataclasses import dataclass

try:
    from faker import Faker
except ImportError:
    print("Warning: faker not installed. Install with: pip install faker")
    Faker = None

@dataclass
class AppMetric:
    """Data class representing a single app metric record."""
    app_name: str
    platform: str
    date: str
    country: str
    installs: int
    in_app_revenue: float
    ads_revenue: float
    ua_cost: float

class DatabaseManager:
    """Handles database operations for the analytics chatbot."""

    def __init__(self, db_path: str = "chatbot_env/apps.db"):
        """
        Initialize DatabaseManager with specified database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def create_schema(self) -> None:
        """Create the app_metrics table with proper schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT NOT NULL,
                    platform TEXT NOT NULL CHECK (platform IN ('iOS', 'Android')),
                    date DATE NOT NULL,
                    country TEXT NOT NULL,
                    installs INTEGER NOT NULL CHECK (installs >= 0),
                    in_app_revenue REAL NOT NULL CHECK (in_app_revenue >= 0),
                    ads_revenue REAL NOT NULL CHECK (ads_revenue >= 0),
                    ua_cost REAL NOT NULL CHECK (ua_cost >= 0),
                    UNIQUE(app_name, platform, date, country)
                )
            ''')
            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_app_platform ON app_metrics(app_name, platform)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_date ON app_metrics(date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_country ON app_metrics(country)
            ''')

    def generate_sample_data(self, num_records: int = 1000) -> List[AppMetric]:
        """
        Generate realistic sample data for app metrics.

        Args:
            num_records: Number of records to generate

        Returns:
            List of AppMetric objects

        """
        if Faker is None:
            raise ImportError("faker package is required for data generation")

        fake = Faker()
        apps = ['Paint', 'Countdown', 'Puzzle', 'Fitness', 'News']
        platforms = ['iOS', 'Android']
        countries = ['USA', 'UK', 'Germany', 'France', 'India']
        # Weight countries by market size (mathematical logic for realism)
        country_weights = [0.4, 0.2, 0.15, 0.15, 0.1]  # USA dominates, then EU, then India
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2025, 1, 31)

        records = []
        generated_combinations = set()

        for _ in range(num_records):
            max_attempts = 10
            for _ in range(max_attempts):
                app = random.choice(apps)
                platform = random.choice(platforms)
                date = fake.date_between(start_date=start_date, end_date=end_date)
                country = random.choices(countries, weights=country_weights, k=1)[0]
                combination_key = (app, platform, date.strftime('%Y-%m-%d'), country)
                if combination_key not in generated_combinations:
                    generated_combinations.add(combination_key)
                    break
            else:
                continue

            base_popularity = random.uniform(0.1, 1.0)  # App popularity factor
            seasonal_factor = 1 + 0.3 * math.sin(date.timetuple().tm_yday * 2 * math.pi / 365)
            installs = max(50, int(base_popularity * seasonal_factor * random.lognormvariate(7, 1)))
            revenue_factor = base_popularity * random.uniform(0.5, 2.0)
            in_app_revenue = max(0, revenue_factor * random.lognormvariate(4, 1))
            ads_revenue = max(0, revenue_factor * 0.7 * random.lognormvariate(3.5, 1))
            ua_cost = max(0, installs * random.uniform(0.1, 0.5) * random.lognormvariate(0, 0.5))

            records.append(AppMetric(
                app_name=app,
                platform=platform,
                date=date.strftime('%Y-%m-%d'),
                country=country,
                installs=installs,
                in_app_revenue=round(in_app_revenue, 2),
                ads_revenue=round(ads_revenue, 2),
                ua_cost=round(ua_cost, 2)
            ))

        return records

    def insert_sample_data(self, records: List[AppMetric]) -> None:
        """Insert sample data into the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Use executemany for better performance
            cursor.executemany('''
                INSERT OR IGNORE INTO app_metrics 
                (app_name, platform, date, country, installs, in_app_revenue, ads_revenue, ua_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [(r.app_name, r.platform, r.date, r.country, r.installs, r.in_app_revenue, r.ads_revenue, r.ua_cost) for r in records])

    def get_table_info(self) -> dict:
        """Get basic information about the database table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM app_metrics")
            total_records = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT app_name) FROM app_metrics")
            unique_apps = cursor.fetchone()[0]
            cursor.execute("SELECT MIN(date), MAX(date) FROM app_metrics")
            date_range = cursor.fetchone()
            return {
                "total_records": total_records,
                "unique_apps": unique_apps,
                "date_range": date_range
            }

    def setup_database(self, num_records: int = 1000) -> None:
        """Complete database setup with schema and sample data."""
        print("Creating database schema...")
        self.create_schema()
        print(f"Generating {num_records} sample records...")
        sample_data = self.generate_sample_data(num_records)
        print("Inserting sample data...")
        self.insert_sample_data(sample_data)
        info = self.get_table_info()
        print(f"Database setup complete!")
        print(f"Total records: {info['total_records']}")
        print(f"Unique apps: {info['unique_apps']}")
        print(f"Date range: {info['date_range'][0]} to {info['date_range'][1]}")

def main() -> None:
    db_manager = DatabaseManager()
    db_manager.setup_database(num_records=10)

if __name__ == '__main__':
    main()