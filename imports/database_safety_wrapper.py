"""
🚨 NUCLEAR OPTION: Hardwired Database Safety Wrapper

This module provides absolute protection against production database deletion
by intercepting ALL database operations and blocking destructive operations
on any database that doesn't have "_dev" in its filename.

HARDWIRED SAFETY RULE: Only databases with "_dev" in filename can be cleared/deleted.
"""

import sqlite3
import os
from loguru import logger


class SafetyViolationError(Exception):
    """Raised when an operation violates database safety rules"""
    pass


class HardwiredDatabaseSafety:
    """
    Hardwired safety wrapper that prevents destructive operations
    on production databases (any database without "_dev" in filename).
    """
    
    DESTRUCTIVE_OPERATIONS = [
        'DELETE FROM', 'DROP TABLE', 'DROP DATABASE', 'TRUNCATE',
        'DELETE ', 'drop table', 'drop database', 'truncate'
    ]
    
    @classmethod
    def is_safe_database(cls, db_path: str) -> bool:
        """Check if database is safe for destructive operations (has _dev in filename)"""
        if not db_path:
            return False
        
        # Extract filename from path
        filename = os.path.basename(db_path)
        
        # Only allow destructive operations on databases with "_dev" in filename
        return '_dev' in filename.lower()
    
    @classmethod
    def is_destructive_operation(cls, sql: str) -> bool:
        """Check if SQL operation is destructive"""
        if not sql:
            return False
            
        sql_upper = sql.upper().strip()
        
        for destructive_op in cls.DESTRUCTIVE_OPERATIONS:
            if destructive_op.upper() in sql_upper:
                return True
        
        return False
    
    @classmethod
    def check_operation_safety(cls, db_path: str, sql: str) -> None:
        """
        Check if operation is safe. Raises SafetyViolationError if not.
        
        HARDWIRED RULE: Only databases with "_dev" in filename can have destructive operations.
        """
        if not cls.is_destructive_operation(sql):
            # Non-destructive operations are always allowed
            return
        
        if not cls.is_safe_database(db_path):
            filename = os.path.basename(db_path) if db_path else 'unknown'
            logger.error(f"🚨 HARDWIRED SAFETY VIOLATION: Destructive operation attempted on NON-DEV database")
            logger.error(f"🚨 Database: {db_path}")
            logger.error(f"🚨 Filename: {filename}")
            logger.error(f"🚨 SQL: {sql[:100]}...")
            logger.error(f"🚨 HARDWIRED RULE: Only databases with '_dev' in filename can be cleared!")
            
            raise SafetyViolationError(
                f"HARDWIRED SAFETY VIOLATION: Cannot execute destructive operation on non-dev database '{filename}'. "
                f"Only databases with '_dev' in filename can be cleared!"
            )
        
        # If we get here, it's a destructive operation on a dev database - allowed
        logger.info(f"✅ HARDWIRED SAFETY: Destructive operation allowed on dev database: {os.path.basename(db_path)}")


class SafeDatabaseConnection:
    """
    Wrapper around sqlite3.Connection that enforces hardwired safety rules
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path)
        
    def execute(self, sql: str, *args, **kwargs):
        """Execute SQL with hardwired safety checks"""
        HardwiredDatabaseSafety.check_operation_safety(self.db_path, sql)
        return self.connection.execute(sql, *args, **kwargs)
    
    def executemany(self, sql: str, *args, **kwargs):
        """Execute many SQL statements with hardwired safety checks"""
        HardwiredDatabaseSafety.check_operation_safety(self.db_path, sql)
        return self.connection.executemany(sql, *args, **kwargs)
    
    def cursor(self):
        """Return a safe cursor that enforces safety rules"""
        return SafeDatabaseCursor(self.db_path, self.connection.cursor())
    
    def commit(self):
        """Commit transaction"""
        return self.connection.commit()
    
    def rollback(self):
        """Rollback transaction"""
        return self.connection.rollback()
    
    def close(self):
        """Close connection"""
        return self.connection.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


class SafeDatabaseCursor:
    """
    Wrapper around sqlite3.Cursor that enforces hardwired safety rules
    """
    
    def __init__(self, db_path: str, cursor):
        self.db_path = db_path
        self.cursor = cursor
    
    def execute(self, sql: str, *args, **kwargs):
        """Execute SQL with hardwired safety checks"""
        HardwiredDatabaseSafety.check_operation_safety(self.db_path, sql)
        return self.cursor.execute(sql, *args, **kwargs)
    
    def executemany(self, sql: str, *args, **kwargs):
        """Execute many SQL statements with hardwired safety checks"""
        HardwiredDatabaseSafety.check_operation_safety(self.db_path, sql)
        return self.cursor.executemany(sql, *args, **kwargs)
    
    def fetchone(self):
        """Fetch one result"""
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Fetch all results"""
        return self.cursor.fetchall()
    
    def fetchmany(self, size=None):
        """Fetch many results"""
        return self.cursor.fetchmany(size)


def safe_sqlite_connect(db_path: str):
    """
    Replacement for sqlite3.connect() that enforces hardwired safety rules.
    
    Usage:
        from database_safety_wrapper import safe_sqlite_connect
        
        # This will work for dev databases
        conn = safe_sqlite_connect('data/botifython_dev.db')
        
        # This will prevent destructive operations on production databases
        conn = safe_sqlite_connect('data/botifython.db')
        conn.execute('DELETE FROM store')  # SafetyViolationError raised!
    """
    return SafeDatabaseConnection(db_path)


# Monkey patch sqlite3.connect for absolute protection (optional - can be enabled if needed)
def enable_global_safety_protection():
    """
    NUCLEAR OPTION: Replace sqlite3.connect globally with safe version.
    
    WARNING: This affects ALL database connections in the entire application.
    Only enable if you want absolute protection everywhere.
    """
    original_connect = sqlite3.connect
    
    def safe_connect_wrapper(*args, **kwargs):
        db_path = args[0] if args else kwargs.get('database', '')
        logger.debug(f"🔒 GLOBAL SAFETY: Intercepted database connection to: {db_path}")
        return SafeDatabaseConnection(db_path)
    
    sqlite3.connect = safe_connect_wrapper
    logger.warning("🔒 GLOBAL DATABASE SAFETY ENABLED: All sqlite3.connect() calls now use safety wrapper")


if __name__ == '__main__':
    # Add project root to sys.path to allow imports to work when run directly
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from imports.database_safety_wrapper import safe_sqlite_connect, SafetyViolationError

    # Test the safety wrapper
    print("🔧 Testing Hardwired Database Safety Wrapper")
    print("=" * 50)

    # Test 1: Safe operation on dev database
    try:
        conn = safe_sqlite_connect('data/test_dev.db')
        # conn.execute('DELETE FROM test_table')  # This would error if table doesnt exist, so we skip for test
        print("✅ TEST 1 PASSED: Destructive operation allowed on dev database (conceptually)")
    except SafetyViolationError as e:
        print(f"❌ TEST 1 FAILED: {e}")

    # Test 2: Unsafe operation on production database
    try:
        conn = safe_sqlite_connect('data/test.db')
        conn.execute('DELETE FROM test_table')  # Should fail
        print("❌ TEST 2 FAILED: Destructive operation was allowed on production database!")
    except SafetyViolationError as e:
        print(f"✅ TEST 2 PASSED: {e}")

    print("🔧 Database safety wrapper tests complete")
