import os
import json
import logging
from typing import Dict, List
import streamlit as st
from dotenv import load_dotenv
from jsonc_parser.parser import JsoncParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DEFAULT_CONSTRAINTS_PATH = os.getenv("USER_CONSTRAINTS_PATH")

def load_file_data(filepath: str) -> Dict[str, List[str]]:
    """Loads constraints JSONC/JSON safely."""
    if not filepath or not os.path.exists(filepath):
        st.error(f"Target file not found at `{filepath}`")
        return {}
    try:
        data = JsoncParser().parse_file(filepath)
        if isinstance(data, dict):
            cleaned_data = {}
            for k, v in data.items():
                if isinstance(v, list):
                    cleaned_data[str(k)] = [str(item) for item in v]
                else:
                    cleaned_data[str(k)] = []
            return cleaned_data
    except Exception as e:
        st.error(f"Error parsing file `{filepath}`: {e}")
    return {}

def save_file_data(data: Dict[str, List[str]], filepath: str) -> bool:
    """Saves constraints to JSONC file formatted cleanly."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.write("\n")
        return True
    except Exception as e:
        st.error(f"Failed to save file `{filepath}`: {e}")
        return False

def inject_beforeunload_alert(is_dirty: bool):
    """Injects JS beforeunload handler to prompt user on page reload / tab close when changes are unsaved."""
    status_bool = "true" if is_dirty else "false"
    js_code = f"""
    <script>
        (function() {{
            try {{
                const targetWindow = window.parent || window.top || window;
                if ({status_bool}) {{
                    targetWindow.onbeforeunload = function(e) {{
                        const msg = "You have unsaved changes! Are you sure you want to leave?";
                        e = e || targetWindow.event;
                        if (e) {{
                            e.returnValue = msg;
                        }}
                        return msg;
                    }};
                }} else {{
                    targetWindow.onbeforeunload = null;
                }}
            }} catch (err) {{
                console.log("Unable to attach beforeunload event:", err);
            }}
        }})();
    </script>
    """
    st.html(js_code, unsafe_allow_javascript=True)

def check_dirty():
    current = json.dumps(st.session_state.constraints, sort_keys=True)
    is_dirty = (current != st.session_state.initial_constraints)
    st.session_state.is_dirty = is_dirty
    inject_beforeunload_alert(is_dirty)

def reset_to_file():
    loaded = load_file_data(st.session_state.filepath)
    st.session_state.constraints = loaded
    st.session_state.initial_constraints = json.dumps(loaded, sort_keys=True)
    st.session_state.is_dirty = False
    inject_beforeunload_alert(False)
    st.toast("Reverted changes to disk state!", icon="🔄")

def main():
    st.set_page_config(
        page_title="TechPulse Constraints Manager",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for modern styling
    st.markdown("""
    <style>
        .main-header {
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .sub-header {
            color: #6B7280;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }
        .dirty-badge {
            background-color: #FEF3C7;
            color: #92400E;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
        }
        .saved-badge {
            background-color: #D1FAE5;
            color: #065F46;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
        }
    </style>
    """, unsafe_allow_html=True)

    # Session State Initialization
    if "filepath" not in st.session_state:
        st.session_state.filepath = DEFAULT_CONSTRAINTS_PATH or "src/data/user_constraints.jsonc"

    if "constraints" not in st.session_state or "initial_constraints" not in st.session_state:
        loaded = load_file_data(st.session_state.filepath)
        st.session_state.constraints = loaded
        st.session_state.initial_constraints = json.dumps(loaded, sort_keys=True)
        st.session_state.is_dirty = False

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="main-header">User Constraints</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Manage categories and semantic filter phrases for your recommendation engine</div>', unsafe_allow_html=True)

        # Quick Summary Statistics in Sidebar
        total_categories = len(st.session_state.constraints)
        total_phrases = sum(len(phrases) for phrases in st.session_state.constraints.values())
        avg_phrases = round(total_phrases / total_categories, 1) if total_categories > 0 else 0

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("Categories", total_categories)
        with col_s2:
            st.metric("Phrases", total_phrases)

        st.markdown("---")
        
        # Sidebar Navigation Menu
        nav_option = st.radio(
            "Navigation",
            options=[
                "📁 Category Management", 
                "📝 Phrase Management", 
                "🔍 Search & Browse", 
                "📄 Raw JSON Preview"
            ],
            key="sidebar_navigation"
        )
        
        st.markdown("---")
        
        # Save & Status Controls
        check_dirty()
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("💾 Save File", type="primary", use_container_width=True, disabled=not st.session_state.is_dirty):
                if save_file_data(st.session_state.constraints, st.session_state.filepath):
                    st.session_state.initial_constraints = json.dumps(st.session_state.constraints, sort_keys=True)
                    st.session_state.is_dirty = False
                    st.toast("Saved successfully!", icon="✅")
                    st.rerun()
        
        with col_reset:
            if st.button("🔄 Discard", use_container_width=True, disabled=not st.session_state.is_dirty):
                reset_to_file()
                st.rerun()

        st.markdown("---")

    # Main Screen Header and Content
    st.subheader(nav_option)

    if st.session_state.is_dirty:
        st.warning("⚠️ **Unsaved Changes Detected**: You have unsaved edits. Click **💾 Save File** in the sidebar to persist your changes, or **🔄 Discard** to revert.")

    # 1. CATEGORY MANAGEMENT
    if nav_option == "📁 Category Management":
        cat_tab_add, cat_tab_rename, cat_tab_delete = st.tabs([
            "➕ Add Category", "✏️ Rename Category", "🗑️ Delete Category"
        ])
        
        # Add Category
        with cat_tab_add:
            st.subheader("Add New Category")
            new_cat_name = st.text_input("Category Name", placeholder="e.g. quantum_computing", key="add_cat_input")
            initial_phrase_input = st.text_input("Initial Phrase (Optional)", placeholder="e.g. quantum algorithms and qpu", key="add_cat_phrase_input")
            
            if st.button("➕ Create Category", type="primary"):
                cleaned_cat = new_cat_name.strip()
                if not cleaned_cat:
                    st.error("Category name cannot be empty.")
                elif cleaned_cat in st.session_state.constraints:
                    st.error(f"Category `{cleaned_cat}` already exists.")
                else:
                    st.session_state.constraints[cleaned_cat] = []
                    if initial_phrase_input.strip():
                        st.session_state.constraints[cleaned_cat].append(initial_phrase_input.strip())
                    check_dirty()
                    st.toast(f"Category `{cleaned_cat}` created!", icon="🎉")
                    st.rerun()

        # Rename Category
        with cat_tab_rename:
            st.subheader("Rename Existing Category")
            cats = list(st.session_state.constraints.keys())
            if not cats:
                st.info("No categories available.")
            else:
                cat_to_rename = st.selectbox("Select Category to Rename", options=cats, key="rename_cat_select")
                new_renamed_val = st.text_input("New Category Name", value=cat_to_rename, key=f"rename_input_{cat_to_rename}")
                
                if st.button("✏️ Rename Category", type="primary"):
                    cleaned_renamed = new_renamed_val.strip()
                    if not cleaned_renamed:
                        st.error("Category name cannot be empty.")
                    elif cleaned_renamed == cat_to_rename:
                        st.info("No name change detected.")
                    elif cleaned_renamed in st.session_state.constraints:
                        st.error(f"Category `{cleaned_renamed}` already exists.")
                    else:
                        new_dict = {}
                        for k, v in st.session_state.constraints.items():
                            if k == cat_to_rename:
                                new_dict[cleaned_renamed] = v
                            else:
                                new_dict[k] = v
                        st.session_state.constraints = new_dict
                        check_dirty()
                        st.toast(f"Renamed `{cat_to_rename}` to `{cleaned_renamed}`", icon="✏️")
                        st.rerun()

        # Delete Category
        with cat_tab_delete:
            st.subheader("Delete Category")
            cats = list(st.session_state.constraints.keys())
            if not cats:
                st.info("No categories available.")
            else:
                cat_to_del = st.selectbox("Select Category to Delete", options=cats, key="del_cat_select")
                phrase_count = len(st.session_state.constraints.get(cat_to_del, []))
                
                st.warning(f"⚠️ Deleting category `{cat_to_del}` will remove it along with all {phrase_count} phrases contained inside it.")
                confirm_del = st.checkbox(f"I confirm I want to permanently delete category `{cat_to_del}`")
                
                if st.button("🗑️ Delete Category", type="primary", disabled=not confirm_del):
                    del st.session_state.constraints[cat_to_del]
                    check_dirty()
                    st.toast(f"Deleted category `{cat_to_del}`", icon="🗑️")
                    st.rerun()

    # 2. PHRASE MANAGEMENT
    elif nav_option == "📝 Phrase Management":
        categories = list(st.session_state.constraints.keys())
        if not categories:
            st.warning("No categories found. Please add a category first in 'Category Management'.")
        else:
            selected_cat = st.selectbox("Select Category", options=categories, key="phrase_cat_select")
            
            if selected_cat:
                current_phrases = st.session_state.constraints[selected_cat]
                st.markdown(f"**Current Phrases in `{selected_cat}` ({len(current_phrases)})**")
                
                p_tab_view, p_tab_add, p_tab_edit, p_tab_delete = st.tabs([
                    "👁️ View Phrases", "➕ Add Phrase", "✏️ Edit Phrase", "🗑️ Delete Phrase"
                ])
                
                # View Phrases
                with p_tab_view:
                    if current_phrases:
                        for idx, phrase in enumerate(current_phrases, 1):
                            st.markdown(f"**{idx}.** {phrase}")
                    else:
                        st.info("No phrases in this category yet.")
                
                # Add Phrase
                with p_tab_add:
                    st.subheader("Add New Phrase(s)")
                    add_mode = st.radio("Add Mode", ["Single Phrase", "Bulk Add (One per line)"], horizontal=True)
                    
                    if add_mode == "Single Phrase":
                        new_phrase = st.text_input("Phrase text", placeholder="e.g. open source LLM benchmarks")
                        if st.button("➕ Add Phrase", type="primary"):
                            cleaned = new_phrase.strip()
                            if not cleaned:
                                st.error("Phrase cannot be empty.")
                            elif cleaned in current_phrases:
                                st.warning("Phrase already exists in this category.")
                            else:
                                st.session_state.constraints[selected_cat].append(cleaned)
                                check_dirty()
                                st.toast(f"Added phrase to `{selected_cat}`", icon="✅")
                                st.rerun()
                    else:
                        bulk_text = st.text_area("Enter phrases (one per line)", height=150, placeholder="phrase 1\nphrase 2\nphrase 3")
                        if st.button("➕ Add Bulk Phrases", type="primary"):
                            added_count = 0
                            for line in bulk_text.splitlines():
                                cleaned = line.strip()
                                if cleaned and cleaned not in st.session_state.constraints[selected_cat]:
                                    st.session_state.constraints[selected_cat].append(cleaned)
                                    added_count += 1
                            if added_count > 0:
                                check_dirty()
                                st.toast(f"Added {added_count} phrases to `{selected_cat}`", icon="✅")
                                st.rerun()
                            else:
                                st.warning("No new phrases were added.")
                
                # Edit Phrase
                with p_tab_edit:
                    st.subheader("Edit Existing Phrase")
                    if not current_phrases:
                        st.info("No phrases available to edit.")
                    else:
                        target_phrase = st.selectbox("Select Phrase to Edit", options=current_phrases, key="edit_phrase_select")
                        if target_phrase:
                            updated_phrase_val = st.text_input("New text", value=target_phrase, key=f"edit_input_{selected_cat}_{target_phrase}")
                            if st.button("✏️ Update Phrase", type="primary"):
                                cleaned_up = updated_phrase_val.strip()
                                if not cleaned_up:
                                    st.error("Phrase text cannot be empty.")
                                elif cleaned_up == target_phrase:
                                    st.info("No changes made.")
                                else:
                                    idx = st.session_state.constraints[selected_cat].index(target_phrase)
                                    st.session_state.constraints[selected_cat][idx] = cleaned_up
                                    check_dirty()
                                    st.toast("Updated phrase successfully!", icon="✅")
                                    st.rerun()

                # Delete Phrase
                with p_tab_delete:
                    st.subheader("Delete Phrase(s)")
                    if not current_phrases:
                        st.info("No phrases available to delete.")
                    else:
                        del_phrases = st.multiselect("Select Phrase(s) to Delete", options=current_phrases, key="del_phrases_select")
                        if st.button("🗑️ Delete Selected Phrases", type="primary", disabled=not del_phrases):
                            for p in del_phrases:
                                if p in st.session_state.constraints[selected_cat]:
                                    st.session_state.constraints[selected_cat].remove(p)
                            check_dirty()
                            st.toast(f"Deleted {len(del_phrases)} phrase(s)", icon="🗑️")
                            st.rerun()

    # 3. SEARCH & BROWSE
    elif nav_option == "🔍 Search & Browse":
        query = st.text_input("🔍 Search phrases across all categories", placeholder="e.g. Claude, benchmark, security...")
        
        matching_results = []
        for cat, phrases in st.session_state.constraints.items():
            for p in phrases:
                if not query or query.lower() in p.lower() or query.lower() in cat.lower():
                    matching_results.append({"Category": cat, "Phrase": p})
        
        st.markdown(f"**Found {len(matching_results)} matching phrase(s)**")
        
        if matching_results:
            import pandas as pd
            df = pd.DataFrame(matching_results)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No matching phrases found.")

    # 4. RAW JSON PREVIEW
    elif nav_option == "📄 Raw JSON Preview":
        st.json(st.session_state.constraints)

def run_app():
    """Entry point for running the Streamlit app via command line / console script."""
    import sys
    import os

    # Reconfigure stdout/stderr to UTF-8 on Windows to prevent cp1252 UnicodeEncodeError
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    from streamlit.web import cli as stcli
    file_path = os.path.abspath(__file__)
    sys.exit(stcli.main(prog_name="streamlit", args=["run", file_path] + sys.argv[1:]))


if __name__ == "__main__":
    if st.runtime.exists():
        main()
    else:
        run_app()

