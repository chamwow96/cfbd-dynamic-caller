# Dynamic Call V10: Creating mechanism for prod env API key fetch so user doesn't have to hardcode it.

import streamlit as st
import cfbd
from cfbd.rest import ApiException
import pandas as pd
import inspect
from typing import get_type_hints, Union, List, Optional, get_origin, get_args
from datetime import datetime
import json
from enum import Enum

# Page configuration
st.set_page_config(page_title="CFBD API Dynamic Caller V10", layout="wide")

def get_api_key_from_secrets_or_env():
    """Retrieve API key from Streamlit secrets (preferred) or environment variables as a fallback."""
    try:
        # Common secret keys to check at top-level of st.secrets
        candidates = ["BEARER_TOKEN", "CFBD_API_KEY", "API_KEY", "cfbd_bearer_token"]
        for k in candidates:
            if k in st.secrets:
                return st.secrets[k]

        # Check for nested mapping, e.g. st.secrets["cfbd"] = {"BEARER_TOKEN": "xxx"}
        if "cfbd" in st.secrets and isinstance(st.secrets["cfbd"], dict):
            for k in ("BEARER_TOKEN", "api_key", "apiKey", "token"):
                if k in st.secrets["cfbd"]:
                    return st.secrets["cfbd"][k]
    except Exception:
        # If Streamlit secrets isn't available for some reason, ignore and fallback to env
        pass

    # Fallback to environment variable
    import os
    return os.environ.get("BEARER_TOKEN", "") or os.environ.get("CFBD_API_KEY", "")

# Initialize API configuration
@st.cache_resource
def init_cfbd_api():
    """Initialize CFBD API client with configuration using secrets/env var."""
    access_token = get_api_key_from_secrets_or_env()
    configuration = cfbd.Configuration(
        access_token=access_token
    )
    return cfbd.ApiClient(configuration)

# Available API classes with their endpoints
API_CLASSES = {
    "BettingApi": cfbd.BettingApi,
    "CoachesApi": cfbd.CoachesApi,
    "ConferencesApi": cfbd.ConferencesApi,
    "DrivesApi": cfbd.DrivesApi,
    "DraftApi": cfbd.DraftApi,
    "GamesApi": cfbd.GamesApi,
    "MetricsApi": cfbd.MetricsApi,
    "PlayersApi": cfbd.PlayersApi,
    "PlaysApi": cfbd.PlaysApi,
    "RankingsApi": cfbd.RankingsApi,
    "RatingsApi": cfbd.RatingsApi,
    "RecruitingApi": cfbd.RecruitingApi,
    "StatsApi": cfbd.StatsApi,
    "TeamsApi": cfbd.TeamsApi,
    "VenuesApi": cfbd.VenuesApi,
}


def get_enum_values(enum_class):
    """Extract enum values as strings"""
    try:
        if hasattr(enum_class, '__members__'):
            return list(enum_class.__members__.keys())
        return []
    except:
        return []

def get_method_parameters(api_class, method_name):
    """
    Inspect method signature and return parameter details
    Returns: dict with param_name -> {type, required, default, enum_values}
    """
    try:
        method = getattr(api_class, method_name)
        sig = inspect.signature(method)
        type_hints = {}
        
        # Try to get type hints
        try:
            type_hints = get_type_hints(method)
        except:
            pass
        
        params = {}
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs', '_return_http_data_only', 
                             '_preload_content', '_request_timeout', 'async_req']:
                continue
            
            param_info = {
                'required': param.default == inspect.Parameter.empty,
                'default': None if param.default == inspect.Parameter.empty else param.default,
                'type': 'str',
                'enum_values': []
            }
            
            # Get annotation from type hints or parameter
            annotation = type_hints.get(param_name, param.annotation)
            
            if annotation != inspect.Parameter.empty:
                # Handle Optional types like Optional[int]
                origin = get_origin(annotation)
                if origin is Union:
                    args = get_args(annotation)
                    # Get the non-None type
                    annotation = next((arg for arg in args if arg is not type(None)), annotation)
                    origin = get_origin(annotation)
                
                # Determine type
                if annotation == int or annotation is int:
                    param_info['type'] = 'int'
                elif annotation == float or annotation is float:
                    param_info['type'] = 'float'
                elif annotation == bool or annotation is bool:
                    param_info['type'] = 'bool'
                elif annotation == str or annotation is str:
                    param_info['type'] = 'str'
                elif inspect.isclass(annotation) and issubclass(annotation, Enum):
                    param_info['type'] = 'enum'
                    param_info['enum_values'] = get_enum_values(annotation)
                elif origin is list:
                    # Check inner type of list
                    inner_args = get_args(annotation)
                    if inner_args:
                        inner = inner_args[0]
                        if inspect.isclass(inner) and issubclass(inner, Enum):
                            param_info['type'] = 'list_enum'
                            param_info['enum_values'] = get_enum_values(inner)
                        elif inner == int:
                            param_info['type'] = 'list_int'
                        elif inner == float:
                            param_info['type'] = 'list_float'
                        else:
                            param_info['type'] = 'list'
                    else:
                        param_info['type'] = 'list'
            
            params[param_name] = param_info
        
        return params
    except Exception as e:
        st.error(f"Error inspecting method: {e}")
        return {}

def flatten_response(obj, parent_key='', sep='_'):
    """
    Recursively flatten nested API responses into a flat dictionary
    Handles lists, dicts, and enum objects
    """
    items = []
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.extend(flatten_response(v, new_key, sep=sep).items())
    elif isinstance(obj, list):
        if not obj:
            return {parent_key: None}
        # If list contains simple types, join them
        if all(isinstance(item, (str, int, float, bool, type(None))) for item in obj):
            return {parent_key: ', '.join(map(str, obj))}
        # Otherwise flatten each item
        for i, item in enumerate(obj):
            new_key = f"{parent_key}{sep}{i}"
            items.extend(flatten_response(item, new_key, sep=sep).items())
    elif hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool)):
        # Handle objects with attributes (like API response objects)
        obj_dict = {}
        for k, v in obj.__dict__.items():
            # Skip internal Python/Pydantic fields
            if k.startswith('_'):
                continue
            obj_dict[k] = v
        items.extend(flatten_response(obj_dict, parent_key, sep=sep).items())
    else:
        # Handle enums and simple types
        if hasattr(obj, 'value'):
            return {parent_key: obj.value}
        return {parent_key: obj}
    
    return dict(items)

def convert_value(value, expected_type, enum_values=None):
    """Convert input to expected type.
    Supports:
      - single values (str/int/float/bool)
      - comma-separated strings for list types
      - python lists (from multiselects)
    """
    if value is None or value == '':
        return None

    # If value is already a list (e.g., from multiselect) - convert elements as needed
    if isinstance(value, list):
        # Trim strings
        def conv_elem(v):
            if isinstance(v, str):
                v = v.strip()
            if expected_type in ('list_int',) :
                try:
                    return int(v)
                except:
                    return v
            if expected_type in ('list_float',):
                try:
                    return float(v)
                except:
                    return v
            return v
        return [conv_elem(v) for v in value]

    try:
        if expected_type == 'int':
            return int(value)
        elif expected_type == 'float':
            return float(value)
        elif expected_type == 'bool':
            if value == 'True' or value is True:
                return True
            elif value == 'False' or value is False:
                return False
            else:
                return None
        elif expected_type in ('enum',):
            # single enum value expected (string)
            return str(value)
        elif expected_type in ('list', 'list_enum'):
            # Accept comma-separated strings and return list
            if isinstance(value, str):
                return [v.strip() for v in value.split(',') if v.strip() != '']
            return value
        elif expected_type == 'list_int':
            if isinstance(value, str):
                return [int(v.strip()) for v in value.split(',') if v.strip().isdigit()]
            elif isinstance(value, list):
                return [int(v) for v in value]
            else:
                return [int(value)]
        elif expected_type == 'list_float':
            if isinstance(value, str):
                return [float(v.strip()) for v in value.split(',') if v.strip() != '']
            elif isinstance(value, list):
                return [float(v) for v in value]
            else:
                return [float(value)]
        else:
            return str(value)
    except:
        return None

def generate_csv_filename(api_class_name, method_name, years, teams):
    """Generate descriptive CSV filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Year range
    if years:
        year_str = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])
    else:
        year_str = "all"
    
    # Teams (limit to 5)
    if teams and len(teams) > 0:
        team_str = '_'.join(teams[:5])
        if len(teams) > 5:
            team_str += "-etc"
    else:
        team_str = "all"
    
    filename = f"{api_class_name}_{method_name}_{year_str}_{team_str}_{timestamp}.csv"
    return filename

# Streamlit UI
st.title("🏈 CFBD Dynamic API Caller V10")
st.markdown("**Easier-to-use interface for College Football Data API**")

# Sidebar for API configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Acquire API key from Streamlit secrets or environment (hidden)
    api_key = get_api_key_from_secrets_or_env()
    if api_key:
        # Use key silently and inform the user that a hidden key is configured
        configuration = cfbd.Configuration(access_token=api_key)
        api_client = cfbd.ApiClient(configuration)
        st.success("✅ Using a hidden CFBD API key configured on the Streamlit server.")
        st.caption("Key is loaded from Streamlit Secrets or BEARER_TOKEN env var and is not displayed here.")
    else:
        # If no key is found, surface a message for the deployer/admin
        st.warning("⚠️ No CFBD API key found in Streamlit secrets or BEARER_TOKEN env var.")
        st.info("Set a hidden secret (e.g., BEARER_TOKEN) on the Streamlit sharing/deploy environment or provide a BEARER_TOKEN env var.")
        api_client = init_cfbd_api()

# Main interface
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1️⃣ Select API Endpoint")
    
    # Select API class
    selected_api_class = st.selectbox(
        "API Class",
        options=list(API_CLASSES.keys()),
        help="Choose the API category"
    )
    
    # Get available methods for selected class
    api_class = API_CLASSES[selected_api_class](api_client)
    available_methods = [method for method in dir(api_class) 
                        if not method.startswith('_') and callable(getattr(api_class, method))]
    
    selected_method = st.selectbox(
        "API Method",
        options=available_methods,
        help="Choose the specific endpoint"
    )
    
    # Get method parameters
    params = get_method_parameters(api_class.__class__, selected_method)
    
    st.info(f"📊 **{len(params)}** parameters detected")

with col2:
    st.subheader("2️⃣ Configure Parameters")
    
    # Multi-year and multi-team support
    use_multi_year = st.checkbox("Enable Multi-Year Query", value=False)
    use_multi_team = st.checkbox("Enable Multi-Team Query", value=False)
    
    # Initialize lists (will be populated by multiselects or fallbacks)
    years_list = []
    teams_list = []
    
    if use_multi_year:
        # Populate a reasonable year range (adjust start year if you want)
        current_year = datetime.now().year
        # Example start year is 2003, change as needed
        year_options = list(range(2003, current_year + 1))
        # Provide a multiselect for years
        years_selected = st.multiselect(
            "Select Years",
            options=year_options,
            default=[],
            help="Select one or more years. If none selected, you can enter comma-separated years below.",
            key="years_multiselect"
        )
        if years_selected:
            years_list = sorted(set(years_selected))
        else:
            # Fallback text input (optional): allow the user to paste comma-separated years
            year_input = st.text_input(
                "Or enter Years (comma-separated)",
                placeholder="e.g., 2020,2021,2022",
                help="Enter years separated by commas",
                key="years_text_input"
            )
            if year_input:
                years_list = [int(y.strip()) for y in year_input.split(',') if y.strip().isdigit()]
    
    if use_multi_team:
        # Try to populate team options from the API; requires api_client to be available
        teams_options = []
        try:
            teams_api = cfbd.TeamsApi(api_client)
            # Attempt to call a method that returns teams; method name may vary by client version.
            # Many cfbd clients provide get_teams() or get_teams(year). We'll try without args first.
            resp = None
            try:
                resp = teams_api.get_teams()
            except TypeError:
                # If client expects a year param, try using the most recent year if available
                try:
                    resp = teams_api.get_teams(datetime.now().year)
                except Exception:
                    resp = None
            except Exception:
                resp = None

            if resp:
                for item in resp:
                    if isinstance(item, dict):
                        name = item.get('school') or item.get('name') or item.get('team') or None
                        if name:
                            teams_options.append(name)
                    else:
                        name = getattr(item, 'school', None) or getattr(item, 'name', None) or getattr(item, 'team', None)
                        if name:
                            teams_options.append(name)
                teams_options = sorted(set(teams_options))
        except Exception:
            # If fetching fails, leave teams_options empty and fall back to free-text
            teams_options = []

        if teams_options:
            teams_selected = st.multiselect(
                "Select Teams",
                options=teams_options,
                default=[],
                help="Choose one or more teams from the list. If none selected, you can type teams below.",
                key="teams_multiselect"
            )
            if teams_selected:
                teams_list = teams_selected
            else:
                team_input = st.text_input(
                    "Or enter Teams (comma-separated)",
                    placeholder="e.g., Alabama,Georgia,Ohio State",
                    help="Enter team names separated by commas",
                    key="teams_text_input"
                )
                if team_input:
                    teams_list = [t.strip() for t in team_input.split(',') if t.strip()]
        else:
            # If we couldn't fetch team list, keep the simpler text input fallback
            team_input = st.text_input(
                "Teams (comma-separated)",
                placeholder="e.g., Alabama,Georgia,Ohio State",
                help="Enter team names separated by commas",
                key="teams_text_input_fallback"
            )
            if team_input:
                teams_list = [t.strip() for t in team_input.split(',') if t.strip()]

# Dynamic parameter inputs
st.subheader("3️⃣ Method Parameters")

if params:
    param_values = {}
    
    # Organize parameters into required and optional
    required_params = {k: v for k, v in params.items() if v['required']}
    optional_params = {k: v for k, v in params.items() if not v['required']}
    
    if required_params:
        st.markdown("**Required Parameters**")
        req_col1, req_col2 = st.columns(2)
        
        for i, (param_name, param_info) in enumerate(required_params.items()):
            col = req_col1 if i % 2 == 0 else req_col2
            
            with col:
                # Skip year/team if using multi-mode
                if param_name == 'year' and use_multi_year:
                    st.info(f"✓ `{param_name}` handled by multi-year mode")
                    continue
                if param_name == 'team' and use_multi_team:
                    st.info(f"✓ `{param_name}` handled by multi-team mode")
                    continue
                
                # If parameter is an enum (single or list of enums), prefer multiselect so user can pick multiple values
                if param_info['type'] in ('enum', 'list_enum'):
                    # For single enum types we'll still allow multiple selections; if the API expects a single value user can pick one.
                    chosen = st.multiselect(
                        f"{param_name} * (multiselect supported)",
                        options=param_info.get('enum_values', []),
                        help=f"Type: {param_info['type']} — you can select one or more values",
                        key=f"multiselect_required_{param_name}"
                    )
                    # If user selected one value, you may also allow passing string; but we'll keep list if multiple
                    param_values[param_name] = chosen if chosen else ''
                
                elif param_info['type'] in ('list', 'list_int', 'list_float'):
                    # Accept comma-separated input for arbitrary lists
                    input_val = st.text_input(
                        f"{param_name} * (comma-separated)",
                        help=f"Type: {param_info['type']} — Enter comma-separated values for multiple entries",
                        key=f"required_list_{param_name}"
                    )
                    param_values[param_name] = input_val
                
                elif param_info['type'] == 'bool':
                    param_values[param_name] = st.selectbox(
                        f"{param_name} *",
                        options=['', 'True', 'False'],
                        help=f"Type: Boolean (Required)",
                        key=f"required_bool_{param_name}"
                    )
                else:
                    # For strings and numeric single-values, allow optional multi-value via checkbox
                    allow_multi = st.checkbox(f"Allow multiple values for `{param_name}`", value=False, key=f"multi_{param_name}")
                    if allow_multi:
                        input_val = st.text_input(
                            f"{param_name} * (comma-separated)",
                            help=f"Provide comma-separated values",
                            key=f"required_multi_text_{param_name}"
                        )
                        param_values[param_name] = input_val
                    else:
                        param_values[param_name] = st.text_input(
                            f"{param_name} *",
                            help=f"Type: {param_info['type']} (Required)",
                            key=f"required_text_{param_name}"
                        )
    
    if optional_params:
        with st.expander("📋 Optional Parameters", expanded=False):
            opt_col1, opt_col2 = st.columns(2)
            
            for i, (param_name, param_info) in enumerate(optional_params.items()):
                col = opt_col1 if i % 2 == 0 else opt_col2
                
                with col:
                    # Skip year/team if using multi-mode
                    if param_name == 'year' and use_multi_year:
                        continue
                    if param_name == 'team' and use_multi_team:
                        continue
                    
                    if param_info['type'] in ('enum', 'list_enum'):
                        chosen = st.multiselect(
                            param_name + " (multiselect supported)",
                            options=param_info.get('enum_values', []),
                            help=f"Type: {param_info['type']} — you can select one or more values",
                            key=f"opt_multiselect_{param_name}"
                        )
                        param_values[param_name] = chosen if chosen else ''
                    
                    elif param_info['type'] in ('list', 'list_int', 'list_float'):
                        input_val = st.text_input(
                            param_name,
                            value=str(param_info['default']) if param_info['default'] is not None else '',
                            help=f"Type: {param_info['type']} — comma-separated values for multiple entries",
                            key=f"opt_list_{param_name}"
                        )
                        param_values[param_name] = input_val
                    elif param_info['type'] == 'bool':
                        param_values[param_name] = st.selectbox(
                            param_name,
                            options=['', 'True', 'False'],
                            index=0,
                            help=f"Type: Boolean (Optional)",
                            key=f"opt_bool_{param_name}"
                        )
                    else:
                        allow_multi = st.checkbox(f"Allow multiple values for `{param_name}`", value=False, key=f"opt_multi_{param_name}")
                        if allow_multi:
                            param_values[param_name] = st.text_input(
                                param_name,
                                value=str(param_info['default']) if param_info['default'] is not None else '',
                                help=f"Provide comma-separated values",
                                key=f"opt_multi_text_{param_name}"
                            )
                        else:
                            param_values[param_name] = st.text_input(
                                param_name,
                                value=str(param_info['default']) if param_info['default'] is not None else '',
                                help=f"Type: {param_info['type']} (Optional)",
                                key=f"opt_text_{param_name}"
                            )
else:
    st.info("No parameters required for this endpoint")
    param_values = {}

# Execute API call
st.subheader("4️⃣ Execute")

if st.button("🚀 Call API", type="primary", use_container_width=True):
    try:
        # Determine iteration strategy
        if use_multi_year and years_list:
            year_iterations = years_list
        elif 'year' in param_values and param_values['year']:
            year_iterations = [convert_value(param_values['year'], 'int')]
        else:
            year_iterations = [None]
        
        if use_multi_team and teams_list:
            team_iterations = teams_list
        elif 'team' in param_values and param_values['team']:
            team_iterations = [param_values['team']]
        else:
            team_iterations = [None]
        
        all_results = []
        total_calls = len(year_iterations) * len(team_iterations)
        
        # If some params contain lists / multi-values, adjust total calls to reflect combinations
        multi_param_lists = {}
        for pname, pinfo in params.items():
            # Get prepared value
            val = param_values.get(pname, None)
            if val is None or val == '':
                continue
            # If the stored param value is a list (from multiselect), count it
            if isinstance(val, list) and len(val) > 1:
                multi_param_lists[pname] = val
        
        # We'll multiply through year/team loops; for other multi params we will iterate inner combinations per call
        progress_bar = st.progress(0)
        status_text = st.empty()
        call_count = 0
        base_call_index = 0
        
        for year in year_iterations:
            for team in team_iterations:
                # For parameters with list values, create combinations (cartesian product)
                # Build a list of (pname, values) for multi params
                from itertools import product
                multi_names = list(multi_param_lists.keys())
                multi_values = [multi_param_lists[n] for n in multi_names] if multi_names else [[]]
                
                if multi_names:
                    combos = list(product(*multi_values))
                else:
                    combos = [()]
                
                for combo in combos:
                    call_count += 1
                    status_text.text(f"Processing {call_count}: Year={year}, Team={team}, combo={combo}")
                    
                    # Build call arguments
                    call_args = {}
                    for param_name, param_info in params.items():
                        # Handle multi-year/team
                        if param_name == 'year' and year is not None:
                            call_args['year'] = year
                        elif param_name == 'team' and team is not None:
                            call_args['team'] = team
                        elif param_name in param_values:
                            raw_value = param_values[param_name]
                            # If this param is part of multi_names, fetch the value from combo
                            if param_name in multi_names:
                                idx = multi_names.index(param_name)
                                item_val = combo[idx]
                                # convert single item into appropriate type
                                converted = convert_value(item_val, param_info['type'], param_info.get('enum_values'))
                                if converted is not None:
                                    call_args[param_name] = converted
                            else:
                                converted = convert_value(raw_value, param_info['type'], param_info.get('enum_values'))
                                if converted is not None:
                                    call_args[param_name] = converted
                    
                    # Execute API call
                    method = getattr(api_class, selected_method)
                    response = method(**call_args)
                    
                    # Flatten response
                    if isinstance(response, list):
                        for item in response:
                            flat_item = flatten_response(item)
                            if year is not None:
                                flat_item['year'] = year
                            if team is not None:
                                flat_item['team'] = team
                            # annotate multi param values used for this call
                            for i, pname in enumerate(multi_names):
                                flat_item[pname] = combo[i]
                            all_results.append(flat_item)
                    else:
                        flat_item = flatten_response(response)
                        if year is not None:
                            flat_item['year'] = year
                        if team is not None:
                            flat_item['team'] = team
                        for i, pname in enumerate(multi_names):
                            flat_item[pname] = combo[i]
                        all_results.append(flat_item)
                    
                    # Update progress
                    # Note: total_calls is a lower bound (year*team), not exact if other params have multiple selections
                    progress_bar.progress(min(1.0, call_count / max(1, total_calls)))
        
        # Convert to DataFrame
        if all_results:
            df = pd.DataFrame(all_results)
            
            st.success(f"✅ Successfully retrieved {len(df)} records!")
            
            # Display results
            st.dataframe(df.head(100), use_container_width=True)
            
            if len(df) > 100:
                st.info(f"Showing first 100 rows of {len(df)} total records")
            
            # Generate CSV
            csv_filename = generate_csv_filename(
                selected_api_class,
                selected_method,
                years_list if use_multi_year else ([convert_value(param_values.get('year', ''), 'int')] if 'year' in param_values else []),
                teams_list if use_multi_team else ([param_values.get('team', '')] if 'team' in param_values else [])
            )
            
            csv_data = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True
            )
            
            # Display summary stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Records", len(df))
            col2.metric("Columns", len(df.columns))
            col3.metric("API Calls", call_count)
        else:
            st.warning("No results returned from API")
            
    except ApiException as e:
        st.error(f"❌ API Error: {e}")
        if hasattr(e, 'body'):
            st.code(e.body)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)

# Footer
st.markdown("---")
st.markdown("Built with ❤️ for CFB data analysis | [API Documentation](https://api.collegefootballdata.com/api/docs/?url=/api-docs.json)")
