import os
import sys
import time
import pickle
import pandas as pd
import xlwings as xw
import comtypes.client
import modelgenerator

CURRENT_WORKING_FOLDER = os.path.dirname(os.path.dirname(__file__))
INPUT_SHEET_NAME = "Input"
XLSX_FILE_NAME = "ETABS Model Generator.xlsm"


def main():
    # connect to workbook with xlwings
    file_path = os.path.join(CURRENT_WORKING_FOLDER, XLSX_FILE_NAME)
    workbook = xw.Book(file_path)
    input_sheet = workbook.sheets[INPUT_SHEET_NAME]

    # read user inputs
    df_floors, x_grids, y_grids, df_SFRSbays, df_MF, df_braces, df_walls, model_options = read_user_input(input_sheet)
    
    # create structure object that holds all structural information
    Structure = modelgenerator.Structure(df_floors, x_grids, y_grids, df_SFRSbays, df_MF, df_braces, df_walls, model_options)
    
    # connect to ETABS API
    start_time = time.time()
    SapModel, ETABSObject = ETABS_API_connect()
    SapModel.SetPresentUnits(3) #kip.in
    
    print("Generating stories and grids...")
    Structure.create_elevations(SapModel)  # this MUST be done first
    Structure.create_grids(SapModel)
    SapModel.View.RefreshView(Zoom=False)

    print("Generating floors...")
    Structure.create_floors(SapModel)
    SapModel.View.RefreshView(Zoom=False)
    
    print("Generating frames...")
    Structure.create_frames(SapModel)
    SapModel.View.RefreshView(Zoom=False)
    
    print("Deleting frames outside of floor boundary...")
    Structure.delete_frames(SapModel)
    SapModel.View.RefreshView(Zoom=False)
    
    print("Adding SFRS to model...")
    Structure.add_SFRS(SapModel)
    SapModel.View.RefreshView(Zoom=False)
    
    print("Applying finishing touches...")
    Structure.set_base_fixity(SapModel)
    Structure.set_groups(SapModel)
    SapModel.View.RefreshView(Zoom=False)
    
    # pickle Structure for use later
    pkl_filepath = os.path.join(CURRENT_WORKING_FOLDER, "ModelGeneratorData.pkl")
    with open(pkl_filepath, "wb") as f:
        pickle.dump(Structure, f)
    
    end_time = time.time()
    print("\nModel generated successfully!")
    print("Total elapsed time: {:.2f} seconds".format(end_time - start_time))
    return Structure




def read_user_input(sheet):
    """
    Reads the ETABS model generator spreadsheet and return in either dataframe or dict format
    """
    # floor elevation
    headers = ["floor_name", "floor_height", "floor_elev", "SD_load", "live_load", "cladding_load", "floor_polygon","na","na","na","na", "slab", "girder", "beam", "column"]
    df_floors = pd.DataFrame(sheet.range("C8:Q32").value, columns = headers)
    df_floors = df_floors.dropna(subset=["floor_name"])
    df_floors = df_floors.dropna(axis=1, how = "all")
    df_floors.reset_index(drop=True)
    
    # grid system
    xgrid_name = list(sheet.range("T8:T32").value)
    xgrid_ordinate = list(sheet.range("U8:U32").value)
    x_grids = {str(k):v*12 for k,v in zip(xgrid_name, xgrid_ordinate) if not pd.isna(v)}
    
    ygrid_name = list(sheet.range("V8:V32").value)
    ygrid_ordinate = list(sheet.range("W8:W32").value)
    y_grids = {str(k):v*12 for k,v in zip(ygrid_name, ygrid_ordinate) if not pd.isna(v)}
    
    # SFRS bays
    headers = ["floor_name", "bay_1", "bay_2", "bay_3", "bay_4", "bay_5", "bay_6", "bay_7", "bay_8", "bay_9", "bay_10", "bay_11", "bay_12", "bay_13", "bay_14", "bay_15"]
    df_SFRSbays = pd.DataFrame(sheet.range("C38:R73").value, columns = headers)
    df_SFRSbays = df_SFRSbays.dropna(subset=["floor_name"])
    df_SFRSbays = df_SFRSbays.dropna(axis=1, how = "all")
    df_SFRSbays.reset_index(drop=True)
    
    # moment frame members
    headers = ["x_column", "x_beam", "y_column", "y_beam"]
    df_MF = pd.DataFrame(sheet.range("T38:W73").value, columns = headers)
    df_MF = df_MF.dropna(subset=["x_column"])
    df_MF.reset_index(drop=True)
    if len(df_MF)==0:
        df_MF = None
        
    # brace members
    headers = ["x_brace", "x_config", "y_brace", "y_config"]
    df_braces = pd.DataFrame(sheet.range("Y38:AB73").value, columns = headers)
    df_braces = df_braces.dropna(subset=["x_brace"])
    df_braces.reset_index(drop=True)
    if len(df_braces)==0:
        df_braces = None
    
    # wall members
    headers = ["x_wall", "y_wall"]
    df_walls = pd.DataFrame(sheet.range("AD38:AE73").value, columns = headers)
    df_walls = df_walls.dropna(subset=["x_wall"])
    df_walls.reset_index(drop=True)
    if len(df_walls)==0:
        df_walls = None
    
    # other model options
    model_options = dict()
    model_options["diaphragm_type"] = sheet.range('F76').value
    model_options["base_fixity"] = sheet.range('F77').value
    model_options["enable_REZ"] = sheet.range('F78').value
    model_options["n_infill"] = int(sheet.range('F79').value)
    
    return df_floors, x_grids, y_grids, df_SFRSbays, df_MF, df_braces, df_walls, model_options



def ETABS_API_connect():
    """
    Boiler plate. Attach to currently open ETABS instance using comstype
    """
    helper = comtypes.client.CreateObject('ETABSv1.Helper')
    helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
    try:
        myETABSObject = helper.GetObject("CSI.ETABS.API.ETABSObject")
    except (OSError, comtypes.COMError):
        print("No running instance of the program found or failed to attach.")
        sys.exit(-1)
    SapModel = myETABSObject.SapModel
    return SapModel, myETABSObject



if __name__ == "__main__":
    print("##################################################################################")
    print(r"""
  __  __           _      _  _____                           _             
 |  \/  |         | |    | |/ ____|                         | |            
 | \  / | ___   __| | ___| | |  __  ___ _ __   ___ _ __ __ _| |_ ___  _ __ 
 | |\/| |/ _ \ / _` |/ _ \ | | |_ |/ _ \ '_ \ / _ \ '__/ _` | __/ _ \| '__|
 | |  | | (_) | (_| |  __/ | |__| |  __/ | | |  __/ | | (_| | || (_) | |   
 |_|  |_|\___/ \__,_|\___|_|\_____|\___|_| |_|\___|_|  \__,_|\__\___/|_|   
                                                                           v{}
                                               Copyright Degenkolb Engineers (2025)
        """.format(modelgenerator.__version__)
        )
    print("#################################################################################")
    MAIN_RETURN = main()
