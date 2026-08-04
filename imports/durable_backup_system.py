"""
🎯 DURABLE DATA BACKUP SYSTEM

Whole-database backup solution that ensures critical data (Profiles, Tasks,
AI Keychain, conversation history) survives complete Pipulate repo deletion
and reinstallation.

Key Features:
- 📁 Cross-platform backup location: ~/.pipulate/backups/
- 🛡️ Latest backup kept under the original filename (easy manual restore)
- 📅 Dated copies ({stem}_{YYYY-MM-DD}{suffix}) with 7-day retention
- 🚀 backup_all_databases() is invoked from server.py on startup

History note (2026-07-18): the former per-table merge/restore/soft-delete
lane (backup_table, restore_table, _merge_table_data, auto_backup_all,
auto_restore_all, keychain restore, count methods) was removed. It was dead
by construction — imports/crud.py's _has_backup_fields() always returned
False, so no code path ever exercised it. Recover it from git history only
as reference if a per-record recoverability design is ever undertaken
deliberately, with its own migration probe.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger


class DurableBackupManager:
    """
    🎯 Manages whole-database durable backups that survive repo deletion.

    Backup Strategy:
    - Latest backup: ~/.pipulate/backups/{original_filename}
    - Dated backup: ~/.pipulate/backups/{stem}_{YYYY-MM-DD}{suffix}
    - Retention: dated copies older than 7 days are cleaned up
    """

    def __init__(self, backup_root: Optional[str] = None):
        """Initialize backup manager with cross-platform backup directory."""
        if backup_root:
            self.backup_root = Path(backup_root)
        else:
            # 🎯 Cross-platform: ~/.pipulate/backups/
            # Use OS-independent home directory resolution
            home = Path.home().resolve()  # Resolve symlinks for consistent paths
            self.backup_root = home / '.pipulate' / 'backups'

        # Ensure backup directory exists with proper permissions
        self.backup_root.mkdir(parents=True, exist_ok=True)

        # Set directory permissions (readable/writable by owner only for security)
        if not backup_root:  # Only set permissions if we created the default location
            try:
                import stat
                self.backup_root.chmod(stat.S_IRWXU)  # 700 permissions
            except Exception as e:
                logger.debug(f"Could not set backup directory permissions: {e}")

        logger.info(f"🗃️ Rolling backup root: {self.backup_root}")
        # THE ROSTER IS DERIVED, NOT LITERAL (2026-08-04, fossil-convicted on
        # the maintainer's own box). The app database filename is a pure
        # function of whitelabel.txt: config.py builds data/{APP_NAME.lower()}.db
        # and server.py:322 independently builds the same string. This roster
        # hardcoded 'botifython'. whitelabel.txt here says Pipulate, so the live
        # databases are data/pipulate*.db (mtime Jul 30) while the roster kept
        # copying data/botifython_dev.db (mtime MAY 3) once per server start,
        # forever. The distinct backup stems were ai_keychain / botifython /
        # botifython_dev / discussion: the live Profiles/Tasks database had NEVER
        # been backed up, and the two stale files are exactly what hid it --
        # os.path.exists returned True, no warning fired, and the summary table
        # printed a green checkmark beside a file nobody had touched in three
        # months. A stranger with only one family at least gets a "not found"
        # line in a log. THE DERIVED-PATH RULE: compute the target from an
        # identity value you read and cannot author, so the mismatch becomes
        # unrepresentable instead of merely unlikely.
        try:
            from config import get_app_name
            app_stem = get_app_name().lower()
        except Exception as e:
            # Fail LOUD, then mirror config.py's own basename rule. A silent
            # fallback would be the same disease this patch is curing.
            logger.warning(f"⚠️ Could not resolve app name from config ({e}); "
                           f"deriving the backup roster from the install directory name.")
            root_name = Path(__file__).resolve().parent.parent.name
            app_stem = (root_name[:-5] if root_name.endswith('-main') else root_name).lower()

        # 🎯 CRITICAL DATABASES TO PROTECT
        self.critical_databases = {
            'ai_keychain': {
                'source_path': 'data/ai_keychain.db',
                'description': 'Chip O\'Theseus Memory',
                'critical': True,
                'cross_cutting': True
            },
            'discussion': {
                'source_path': 'data/discussion.db',
                'description': 'Conversation History',
                'critical': True,
                'cross_cutting': True
            },
            'app_prod': {
                'source_path': f'data/{app_stem}.db',
                'description': 'Production Profiles/Tasks',
                'critical': True,
                'cross_cutting': False
            },
            'app_dev': {
                'source_path': f'data/{app_stem}_dev.db',
                'description': 'Development Profiles/Tasks',
                'critical': False,
                'cross_cutting': False
            }
        }

    def backup_all_databases(self) -> Dict[str, bool]:
        """
        🚀 Perform complete backup of all critical databases.

        Called on server startup to ensure all data is protected.
        """
        results = {}
        for key, config in self.critical_databases.items():
            source_path = Path(config["source_path"])
            if os.path.exists(source_path):
                results[key] = self._backup_entire_database(str(source_path))
            else:
                logger.warning(f"⚠️ Source database not found, skipping backup: {source_path}")
                results[key] = False

        self.cleanup_old_backups(keep_days=7)

        successful = sum(1 for success in results.values() if success)
        total = len(self.critical_databases)
        if successful == total:
            logger.info(f"🛡️ Database backup complete: {successful}/{total} successful")
        else:
            logger.warning(f"🛡️ FINDER_TOKEN: BACKUP_STARTUP_PARTIAL - {successful}/{total} databases backed up")

        return results

    def _backup_entire_database(self, source_db_path: str) -> bool:
        """
        📁 Backup an entire database file with original filename strategy.

        Creates two backup files:
        - {original_filename} - Latest backup (for easy manual restore)
        - {stem}_{YYYY-MM-DD}{suffix} - Dated backup (for retention)
        """
        try:
            source_path = Path(source_db_path)
            original_filename = source_path.name

            # Create latest backup (original filename)
            latest_backup = self.backup_root / original_filename
            shutil.copy2(source_path, latest_backup)
            logger.info(f"🛡️ Latest backup created: {latest_backup}")

            # Create dated backup (only if it doesn't exist for today)
            today = datetime.now().strftime('%Y-%m-%d')
            dated_filename = f"{source_path.stem}_{today}{source_path.suffix}"
            dated_backup = self.backup_root / dated_filename

            if not dated_backup.exists():
                shutil.copy2(source_path, dated_backup)
                logger.info(f"🛡️ Dated backup created: {dated_backup}")
            else:
                logger.info(f"🛡️ Dated backup already exists: {dated_backup}")

            return True

        except Exception as e:
            logger.error(f"❌ Database backup failed for {source_db_path}: {e}")
            return False

    def cleanup_old_backups(self, keep_days: int = 7):
        """
        🧹 Clean up dated backup files older than specified days.

        Only removes files with date pattern (filename_YYYY-MM-DD.db).
        Preserves original filename backups (for manual restoration).
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cleaned_count = 0

        for backup_file in self.backup_root.glob("*.db"):
            try:
                # Only process files with date patterns (filename_YYYY-MM-DD.db)
                name_parts = backup_file.stem.split('_')
                if len(name_parts) >= 2:
                    date_str = name_parts[-1]  # Last part should be YYYY-MM-DD

                    # Verify it's a valid date string
                    if len(date_str) == 10 and date_str.count('-') == 2:
                        try:
                            file_date = datetime.strptime(date_str, '%Y-%m-%d')

                            if file_date < cutoff_date:
                                file_size = backup_file.stat().st_size
                                backup_file.unlink()
                                cleaned_count += 1
                                logger.info(f"🧹 Cleaned up old backup: {backup_file} ({file_size / 1024:.1f} KB)")
                        except ValueError:
                            # Not a valid date format, skip (likely original filename backup)
                            continue

            except Exception as e:
                logger.warning(f"⚠️ Error processing backup file {backup_file}: {e}")

        if cleaned_count > 0:
            logger.info(f"🧹 Cleanup complete: Removed {cleaned_count} old backup files (>{keep_days} days)")
        else:
            logger.info(f"🧹 Cleanup complete: No old backup files found (>{keep_days} days)")

    def get_backup_summary_table(self):
        """Generate a Rich Table summarizing the backup status."""
        from rich.table import Table
        table = Table(title="🛡️ Durable Backup Status", border_style="green", show_header=True, header_style="bold green")
        table.add_column("Database", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Backup Path", style="dim")
        for key in ['app_prod', 'app_dev', 'discussion', 'ai_keychain']:
            config = self.critical_databases.get(key)
            if not config: continue
            source_path = Path(config['source_path'])
            backup_path = self.backup_root / source_path.name
            if source_path.exists():
                if backup_path.exists():
                    status = f"✅ Backed Up ({backup_path.stat().st_size / 1024:.1f} KB)"
                else:
                    status = "❌ Not Found"
            else:
                status = "ℹ️ Source Missing"
            table.add_row(config['description'], status, str(backup_path))
        return table


# 🎯 GLOBAL INSTANCE for easy import
backup_manager = DurableBackupManager()
