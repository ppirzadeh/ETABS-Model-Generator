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
    print("Reading user inputs...")
    df_floors, x_grids, y_grids, df_SFRSbays, df_MF, df_braces, df_walls, model_options = read_user_input(input_sheet)
    
    # connect to ETABS API
    start_time = time.time()
    SapModel, ETABSObject = ETABS_API_connect()
    SapModel.SetPresentUnits(3) #kip.in
    
    # unpickle Structure from previous runs
    print("Loading ModelGeneratorData.pkl from previous run...")
    pkl_filepath = os.path.join(CURRENT_WORKING_FOLDER, "ModelGeneratorData.pkl")
    if not os.path.exists(pkl_filepath):
        raise RuntimeError("Could not find ModelGeneratorData.pkl. Did you generate a model previously?")
    with open(pkl_filepath, 'rb') as file:
        Structure = pickle.load(file)
    
    # logic to update section sizes
    index_for = Structure.index_for
    index_for_walls = Structure.index_for_walls
    floor_names = Structure.floor_names
    
    print("Updating section size...")
    for i,floor in enumerate(floor_names):
        gravity_beam = df_floors.loc[i, "beam"]
        gravity_girder = df_floors.loc[i, "girder"]
        gravity_col = df_floors.loc[i, "column"]
        
        # gravity col
        relevant_members = set(index_for[floor]) & set(index_for["column"])
        for uid in relevant_members:
            SapModel.FrameObj.SetSection(Name=uid, PropName=gravity_col)
        
        # gravity girder
        relevant_members = set(index_for[floor]) & set(index_for["girder"])
        for uid in relevant_members:
            SapModel.FrameObj.SetSection(Name=uid, PropName=gravity_girder)
            
        # infill beams
        relevant_members = set(index_for[floor]) & set(index_for["beam"])
        for uid in relevant_members:
            SapModel.FrameObj.SetSection(Name=uid, PropName=gravity_beam)
        
        if df_MF is not None:
            MF_colX = df_MF.loc[i,"x_column"]
            MF_colY = df_MF.loc[i,"y_column"]
            MF_bmX = df_MF.loc[i,"x_beam"]
            MF_bmY = df_MF.loc[i,"y_beam"]
            # SFRS MF beamX
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_beamX"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=MF_bmX)
                
            # SFRS MF beamY
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_beamY"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=MF_bmY)
            
            # SFRS MF colX
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_columnX"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=MF_colX)
            
            # SFRS MF colY
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_columnY"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=MF_colY)
        
        if df_braces is not None:
            braceX = df_braces.loc[i,"x_brace"]
            braceY = df_braces.loc[i,"y_brace"]
            # SFRS braceX
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_braceX"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=braceX)
                
            # SFRS braceY
            relevant_members = set(index_for[floor]) & set(index_for["SFRS_braceY"])
            for uid in relevant_members:
                SapModel.FrameObj.SetSection(Name=uid, PropName=braceY)
                
        if df_walls is not None:
            wallX = df_walls.loc[i,"x_wall"]
            wallY = df_walls.loc[i,"y_wall"]
            # SFRS wallX
            relevant_members = set(index_for_walls[floor]) & set(index_for_walls["SFRS_wallX"])
            for uid in relevant_members:
                SapModel.AreaObj.SetProperty(Name=uid, PropName=wallX)
                
            # SFRS wallY
            relevant_members = set(index_for_walls[floor]) & set(index_for_walls["SFRS_wallY"])
            for uid in relevant_members:
                SapModel.AreaObj.SetProperty(Name=uid, PropName=wallY)
            
    SapModel.View.RefreshView(Zoom=False)
    end_time = time.time()
    print("Done!")
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
