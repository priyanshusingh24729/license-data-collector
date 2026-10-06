"""
Safe, read-only Windows Executable Metadata Extractor.
Extracts PE header / FileVersionInfo metadata (ProductName, CompanyName, FileVersion, FileDescription).
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WindowsExecutableScanner:
    """Extracts application identity metadata from executable binaries."""

    @staticmethod
    def extract_metadata(exe_path: str) -> Dict[str, Optional[str]]:
        """
        Safely extracts file version metadata from an executable path.
        """
        if not exe_path or not os.path.isfile(exe_path):
            return {
                "product_name": None,
                "company_name": None,
                "file_version": None,
                "file_description": None,
            }

        product_name = None
        company_name = None
        file_version = None
        file_desc = None

        # 1. Try win32api if available
        try:
            import win32api
            info = win32api.GetFileVersionInfo(exe_path, "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            file_version = f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"

            # StringFileInfo table extraction
            lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
            str_info_path = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\"
            
            try:
                product_name = win32api.GetFileVersionInfo(exe_path, str_info_path + "ProductName")
            except:
                pass
            try:
                company_name = win32api.GetFileVersionInfo(exe_path, str_info_path + "CompanyName")
            except:
                pass
            try:
                file_desc = win32api.GetFileVersionInfo(exe_path, str_info_path + "FileDescription")
            except:
                pass
        except Exception:
            pass

        # 2. Fallback to basic file path parsing
        if not product_name:
            base = os.path.splitext(os.path.basename(exe_path))[0]
            product_name = base

        return {
            "product_name": product_name,
            "company_name": company_name,
            "file_version": file_version,
            "file_description": file_desc,
        }
