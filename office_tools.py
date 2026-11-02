"""
MS Office Automation Tools for Casper
Uses win32com to natively control Word, Excel, and PowerPoint on Windows.
"""

import os
import asyncio
import logging
from typing import Optional
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("office-tools")

# Attempt to import win32com
try:
    import win32com.client
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logger.warning("win32com.client not available. Please pip install pywin32")

# Default save directory
DEFAULT_SAVE_DIR = os.path.expanduser(r"~\Documents\Cipher\Casper_Docs")
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)


def _init_com():
    """Initializes COM for the current thread."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass


def _uninit_com():
    """Uninitializes COM for the current thread."""
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


def _get_app(app_name: str, visible: bool = False):
    """Helper to dispatch and get the COM app."""
    if not WIN32_AVAILABLE:
        raise RuntimeError("win32com.client is not installed on this system.")
    _init_com()
    app = win32com.client.Dispatch(app_name)
    app.Visible = visible
    return app


# ==========================================
# GENERAL OFFICE TOOLS
# ==========================================

@function_tool()
async def office_close_app(context: RunContext, app_name: str) -> str:
    """
    Close an Office application by name.
    
    Args:
        app_name: "Word", "Excel", or "PowerPoint"
    """
    if not WIN32_AVAILABLE:
        return "win32com not available."
    
    name_map = {
        "word": "Word.Application",
        "excel": "Excel.Application",
        "powerpoint": "PowerPoint.Application"
    }
    
    app_id = name_map.get(app_name.lower())
    if not app_id:
        return f"Unsupported app: {app_name}. Use Word, Excel, or PowerPoint."
        
    try:
        # Get existing instance if running
        app = win32com.client.GetActiveObject(app_id)
        app.Quit()
        return f"Successfully closed {app_name}."
    except Exception as e:
        return f"Failed to close {app_name}. It might not be running. Error: {str(e)}"


# ==========================================
# MICROSOFT WORD TOOLS
# ==========================================

@function_tool()
async def word_create_document(context: RunContext, text: str) -> str:
    """
    Open MS Word, create a new document, and type the provided text.
    
    Args:
        text: The text to insert into the document.
    """
    try:
        word = _get_app("Word.Application", visible=False)
        doc = word.Documents.Add()
        # Insert text at the end of the document
        selection = word.Selection
        selection.TypeText(text)
        
        # Reveal when done
        word.Visible = True
        return "Successfully created Word document and inserted text."
    except Exception as e:
        logger.error(f"Word automation failed: {e}")
        return f"Failed to create Word document: {str(e)}"


def _sync_word_read_active_document() -> str:
    """Synchronous read for MS Word document using COM with UIA fallback."""
    if not WIN32_AVAILABLE:
        return "win32com is not available on this system."
    _init_com()
    
    # 1. Primary: Try Word COM via GetActiveObject
    try:
        word = win32com.client.GetActiveObject("Word.Application")
        if word and word.Documents.Count > 0:
            doc = word.ActiveDocument
            content = doc.Content.Text
            if content and content.strip():
                return f"MS Word Document Content ({doc.Name}):\n{content.strip()}"
            return f"MS Word Document ({doc.Name}) is currently open but empty."
        elif word and word.Documents.Count == 0:
            return "MS Word is open, but no document is currently open in it."
    except Exception as e:
        logger.warning(f"COM GetActiveObject for Word returned: {e}. Trying UIA fallback...")

    # 2. Fallback: Try reading via UI Automation
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                title = w.window_text().strip()
                if "word" in title.lower():
                    for c in w.descendants():
                        if c.element_info.control_type == "Document":
                            try:
                                txt = c.iface_text.DocumentRange.GetText(-1)
                                if txt and txt.strip():
                                    return f"MS Word Document Content ({title}):\n{txt.strip()}"
                            except Exception:
                                pass
                            try:
                                val = c.iface_value.CurrentValue
                                if val and val.strip():
                                    return f"MS Word Document Content ({title}):\n{val.strip()}"
                            except Exception:
                                pass
            except Exception:
                continue
    except Exception as uia_err:
        logger.warning(f"UIA fallback for Word failed: {uia_err}")
    finally:
        _uninit_com()

    return "No active MS Word document could be read. Please ensure Microsoft Word is open with a document loaded."


@function_tool()
async def word_read_active_document(context: RunContext) -> str:
    """
    Read all the text from the currently active Microsoft Word document.
    ALWAYS use this tool whenever the user asks to read, check, summarize, or see what is written in Word.
    """
    return await asyncio.to_thread(_sync_word_read_active_document)


def _sync_notepad_read_active_window() -> str:
    """Synchronous read for active Notepad window using UIA."""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        notepad_win = None

        # Search for any open Notepad window
        for w in desktop.windows():
            try:
                title = w.window_text().strip()
                if "notepad" in title.lower():
                    notepad_win = w
                    break
            except Exception:
                continue

        if not notepad_win:
            return "No open Notepad window was found on your desktop."

        win_title = notepad_win.window_text().strip()
        content = ""

        # Search for Document (Windows 11) or Edit (Windows 10) control
        for control in notepad_win.descendants():
            try:
                c_type = control.element_info.control_type
                if c_type in ["Document", "Edit"]:
                    # Try Value pattern (fastest on Windows 11 Document and Windows 10 Edit)
                    try:
                        val = control.iface_value.CurrentValue
                        if val and val.strip():
                            content = val
                            break
                    except Exception:
                        pass

                    # Try Text pattern
                    try:
                        txt = control.iface_text.DocumentRange.GetText(-1)
                        if txt and txt.strip():
                            content = txt
                            break
                    except Exception:
                        pass

                    # Try window_text
                    try:
                        txt = control.window_text()
                        if txt and txt.strip():
                            content = txt
                            break
                    except Exception:
                        pass
            except Exception:
                continue

        if not content or not content.strip():
            return f"Notepad is open ('{win_title}'), but it appears to be empty."

        return f"Notepad Content ('{win_title}'):\n{content.strip()}"
    except Exception as e:
        logger.error(f"Error reading Notepad window: {e}")
        return f"Failed to read Notepad: {str(e)}"


@function_tool()
async def notepad_read_active_window(context: RunContext) -> str:
    """
    Read all the text from the currently open or active Notepad window.
    ALWAYS use this tool whenever the user asks to read, check, summarize, or see what is written in Notepad.
    """
    return await asyncio.to_thread(_sync_notepad_read_active_window)


def _sync_notepad_write_active_window(new_content: str, append: bool = False) -> str:
    """Updates the open Notepad window's text directly via UIA and syncs to disk if saved."""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        notepad_win = None
        for w in desktop.windows():
            try:
                title = w.window_text().strip()
                if "notepad" in title.lower():
                    notepad_win = w
                    break
            except Exception:
                continue

        if not notepad_win:
            return "No open Notepad window was found on your desktop to edit."

        win_title = notepad_win.window_text().strip()
        updated = False

        for control in notepad_win.descendants():
            try:
                c_type = control.element_info.control_type
                if c_type in ["Document", "Edit"]:
                    final_text = new_content
                    if append:
                        current_val = ""
                        try:
                            current_val = control.iface_value.CurrentValue or ""
                        except Exception:
                            pass
                        if not current_val:
                            try:
                                current_val = control.iface_text.DocumentRange.GetText(-1) or ""
                            except Exception:
                                pass
                        final_text = (current_val.rstrip() + "\r\n\r\n" + new_content.strip()) if current_val.strip() else new_content.strip()

                    # 1. Try SetValue pattern (Windows 11 Document & Windows 10 Edit)
                    try:
                        control.iface_value.SetValue(final_text)
                        updated = True
                        break
                    except Exception:
                        pass

                    # 2. Try set_text (pywinauto Edit wrapper)
                    try:
                        control.set_text(final_text)
                        updated = True
                        break
                    except Exception:
                        pass
            except Exception:
                continue

        if not updated:
            return f"Found Notepad ('{win_title}'), but could not write to its text control."

        # Also check if this Notepad window is associated with a file on Desktop
        saved_msg = ""
        try:
            raw_name = win_title.split("- Notepad")[0].strip().lstrip("*").strip()
            if raw_name and raw_name.lower() != "untitled":
                desktop_file = os.path.join(os.path.expanduser("~"), "Desktop", raw_name)
                if os.path.exists(desktop_file):
                    with open(desktop_file, "w", encoding="utf-8") as f:
                        f.write(final_text)
                    saved_msg = f" (Also synced and saved directly to {desktop_file})"
        except Exception:
            pass

        action = "Appended to" if append else "Updated"
        return f"Successfully {action.lower()} Notepad ('{win_title}') live on screen.{saved_msg}"
    except Exception as e:
        logger.error(f"Error writing to Notepad: {e}")
        return f"Failed to edit Notepad: {str(e)}"


@function_tool()
async def notepad_write_active_window(context: RunContext, new_content: str) -> str:
    """
    Directly updates or replaces the text inside the currently open Notepad window on screen.
    ALWAYS use this tool whenever the user asks to edit, rewrite, update, or change the story/notes in Notepad.
    
    Args:
        new_content: The complete updated text to place into Notepad.
    """
    return await asyncio.to_thread(_sync_notepad_write_active_window, new_content, False)


@function_tool()
async def notepad_append_active_window(context: RunContext, text_to_append: str) -> str:
    """
    Appends text to the end of the currently open Notepad window on screen.
    Use this when the user asks to add something or append text to the current Notepad document.
    
    Args:
        text_to_append: The new text to add to the bottom of the Notepad document.
    """
    return await asyncio.to_thread(_sync_notepad_write_active_window, text_to_append, True)


@function_tool()
async def word_save_document(context: RunContext, file_name: str) -> str:
    """
    Save the currently active MS Word document.
    
    Args:
        file_name: The name of the file (e.g., 'report.docx'). It will be saved in Documents/Cipher/Casper_Docs.
    """
    try:
        word = win32com.client.GetActiveObject("Word.Application")
        if not word.Documents.Count:
            return "No documents are currently open in Word."
        
        doc = word.ActiveDocument
        if not file_name.endswith(".docx"):
            file_name += ".docx"
            
        full_path = os.path.join(DEFAULT_SAVE_DIR, file_name)
        # 16 is wdFormatDocumentDefault
        doc.SaveAs2(full_path, 16)
        return f"Document saved successfully at: {full_path}"
    except Exception as e:
        return f"Failed to save document: {str(e)}"


# ==========================================
# MICROSOFT EXCEL TOOLS
# ==========================================

@function_tool()
async def excel_create_workbook(context: RunContext, data_csv: str) -> str:
    """
    Open MS Excel, create a new workbook, and populate it with comma-separated data.
    
    Args:
        data_csv: Multiline string of comma-separated data to insert.
    """
    try:
        excel = _get_app("Excel.Application", visible=False)
        wb = excel.Workbooks.Add()
        sheet = wb.ActiveSheet
        
        # Parse simple CSV and write to cells
        rows = data_csv.strip().split('\n')
        for r_idx, row in enumerate(rows):
            cols = row.split(',')
            for c_idx, val in enumerate(cols):
                sheet.Cells(r_idx + 1, c_idx + 1).Value = val.strip()
                
        # Auto-fit columns
        sheet.Columns.AutoFit()
        
        # Reveal when done
        excel.Visible = True
        return "Successfully created Excel workbook and inserted data."
    except Exception as e:
        logger.error(f"Excel automation failed: {e}")
        return f"Failed to create Excel workbook: {str(e)}"


@function_tool()
async def excel_read_active_sheet(context: RunContext) -> str:
    """
    Read the used range of the currently active MS Excel worksheet.
    """
    try:
        excel = win32com.client.GetActiveObject("Excel.Application")
        if not excel.Workbooks.Count:
            return "No workbooks are currently open in Excel."
            
        sheet = excel.ActiveSheet
        used_range = sheet.UsedRange
        
        if not used_range:
            return "Active sheet is empty."
            
        # used_range() returns a tuple of tuples representing rows and columns
        data = used_range.Value
        if not data:
            return "Active sheet is empty."
            
        result = []
        # Handle single cell vs multi-cell return values
        if isinstance(data, tuple):
            for row in data:
                row_strs = [str(cell) if cell is not None else "" for cell in row]
                result.append(" | ".join(row_strs))
        else:
            result.append(str(data))
            
        return "Excel Data:\n" + "\n".join(result)
    except Exception as e:
        return f"Failed to read Excel data. Is Excel open? Error: {str(e)}"


# ==========================================
# MICROSOFT POWERPOINT TOOLS
# ==========================================

@function_tool()
async def ppt_create_presentation(context: RunContext, title: str, subtitle: str) -> str:
    """
    Open MS PowerPoint, create a new presentation, and add a title slide.
    
    Args:
        title: Main title for the presentation.
        subtitle: Subtitle for the presentation.
    """
    try:
        ppt = _get_app("PowerPoint.Application", visible=False)
        pres = ppt.Presentations.Add()
        # 1 is ppLayoutTitle
        slide = pres.Slides.Add(1, 1)
        
        slide.Shapes.Title.TextFrame.TextRange.Text = title
        if slide.Shapes.Count >= 2:
            slide.Shapes(2).TextFrame.TextRange.Text = subtitle
            
        # Reveal when done
        ppt.Visible = True
        return "Successfully created PowerPoint presentation."
    except Exception as e:
        logger.error(f"PowerPoint automation failed: {e}")
        return f"Failed to create PowerPoint: {str(e)}"


# Export all tools
OFFICE_TOOLS = [
    office_close_app,
    word_create_document,
    word_read_active_document,
    word_save_document,
    excel_create_workbook,
    excel_read_active_sheet,
    ppt_create_presentation,
    notepad_read_active_window,
    notepad_write_active_window,
    notepad_append_active_window,
]


