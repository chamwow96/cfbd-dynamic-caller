import streamlit as st
import cfbd
from cfbd.rest import ApiException
import pandas as pd
import inspect
from typing import get_type_hints, Union, List, Optional
from datetime import datetime
import json
from enum import Enum

# Page configuration
st.set_page_config(page_title="CFBD API Dynamic Caller V7", layout="wide")

# Initialize API configuration
@st.cache_resource
def init_cfbd_api():
    """Initialize CFBD API client with configuration"""
    import os
    access_token = os.environ.get("BEARER_TOKEN", "")
    configuration = cfbd.Configuration(
        access_token=access_token
    )
    return cfbd.ApiClient(configuration)

# Available API classes with their endpoints
API_CLASSES = {
    "GamesApi": cfbd.GamesApi,
    "TeamsApi": cfbd.TeamsApi,
    "StatsApi": cfbd.StatsApi,
    "RankingsApi": cfbd.RankingsApi,
    "RatingsApi": cfbd.RatingsApi,
    "RecruitingApi": cfbd.RecruitingApi,
    "PlayersApi": cfbd.PlayersApi,
    "PlaysApi": cfbd.PlaysApi,
    "DrivesApi": cfbd.DrivesApi,
    "VenuesApi": cfbd.VenuesApi,
    "CoachesApi": cfbd.CoachesApi,
    "ConferencesApi": cfbd.ConferencesApi,
    "DraftApi": cfbd.DraftApi,
    "MetricsApi": cfbd.MetricsApi,
    "BettingApi": cfbd.BettingApi,
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
            
            # Try to get type annotation
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                
                # Handle Optional types
                if hasattr(annotation, '__origin__'):
                    if annotation.__origin__ is Union:
                        args = annotation.__args__
                        annotation = args[0] if args[0] != type(None) else args[1]
                
                # Determine type
                if annotation == int:
                    param_info['type'] = 'int'
                elif annotation == float:
                    param_info['type'] = 'float'
                elif annotation == bool:
                    param_info['type'] = 'bool'
                elif annotation == str:
                    param_info['type'] = 'str'
                elif hasattr(annotation, '__bases__') and Enum in annotation.__bases__:
                    param_info['type'] = 'enum'
                    param_info['enum_values'] = get_enum_values(annotation)
                elif hasattr(annotation, '__origin__') and annotation.__origin__ is list:
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
    """Convert string input to expected type"""
    if not value or value == '':
        return None
    
    try:
        if expected_type == 'int':
            return int(value)
        elif expected_type == 'float':
            return float(value)
        elif expected_type == 'bool':
            return value.lower() in ['true', '1', 'yes', 'y']
        elif expected_type == 'enum':
            return value
        elif expected_type == 'list':
            return [v.strip() for v in value.split(',')]
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
st.title("🏈 CFBD Dynamic API Caller V7")
st.markdown("**Intelligent interface for College Football Data API**")

# Sidebar for API configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key input
    import os
    api_key = st.text_input("CFBD API Key (Bearer Token)", 
                            type="password",
                            value=os.environ.get("BEARER_TOKEN", ""),
                            help="Get your free API key at collegefootballdata.com")
    
    if api_key:
        configuration = cfbd.Configuration(
            access_token=api_key
        )
        api_client = cfbd.ApiClient(configuration)
        st.success("✅ API Key configured")
    else:
        st.warning("⚠️ Please enter your CFBD API key or set BEARER_TOKEN env var")
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
    
    years_list = []
    teams_list = []
    
    if use_multi_year:
        year_input = st.text_input("Years (comma-separated)", 
                                   placeholder="e.g., 2020,2021,2022",
                                   help="Enter years separated by commas")
        if year_input:
            years_list = [int(y.strip()) for y in year_input.split(',') if y.strip().isdigit()]
    
    if use_multi_team:
        team_input = st.text_input("Teams (comma-separated)", 
                                   placeholder="e.g., Alabama,Georgia,Ohio State",
                                   help="Enter team names separated by commas")
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
                
                if param_info['type'] == 'enum':
                    param_values[param_name] = st.selectbox(
                        f"{param_name} *",
                        options=[''] + param_info['enum_values'],
                        help=f"Type: {param_info['type']}"
                    )
                elif param_info['type'] == 'bool':
                    param_values[param_name] = st.checkbox(
                        f"{param_name} *",
                        value=False
                    )
                else:
                    param_values[param_name] = st.text_input(
                        f"{param_name} *",
                        help=f"Type: {param_info['type']} (Required)"
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
                    
                    if param_info['type'] == 'enum':
                        param_values[param_name] = st.selectbox(
                            param_name,
                            options=[''] + param_info['enum_values'],
                            help=f"Type: {param_info['type']} (Optional)"
                        )
                    elif param_info['type'] == 'bool':
                        param_values[param_name] = st.checkbox(
                            param_name,
                            value=param_info['default'] if param_info['default'] is not None else False
                        )
                    else:
                        param_values[param_name] = st.text_input(
                            param_name,
                            value=str(param_info['default']) if param_info['default'] is not None else '',
                            help=f"Type: {param_info['type']} (Optional)"
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
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        call_count = 0
        
        for year in year_iterations:
            for team in team_iterations:
                call_count += 1
                status_text.text(f"Processing {call_count}/{total_calls}: Year={year}, Team={team}")
                
                # Build call arguments
                call_args = {}
                for param_name, param_info in params.items():
                    # Handle multi-year/team
                    if param_name == 'year' and year is not None:
                        call_args['year'] = year
                    elif param_name == 'team' and team is not None:
                        call_args['team'] = team
                    elif param_name in param_values:
                        value = convert_value(
                            param_values[param_name],
                            param_info['type'],
                            param_info.get('enum_values')
                        )
                        if value is not None:
                            call_args[param_name] = value
                
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
                        all_results.append(flat_item)
                else:
                    flat_item = flatten_response(response)
                    if year is not None:
                        flat_item['year'] = year
                    if team is not None:
                        flat_item['team'] = team
                    all_results.append(flat_item)
                
                progress_bar.progress(call_count / total_calls)
        
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
            col3.metric("API Calls", total_calls)
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
st.markdown("Built with ❤️ for CFBD data analysis | [API Documentation](https://api.collegefootballdata.com/api/docs/?url=/api-docs.json)")