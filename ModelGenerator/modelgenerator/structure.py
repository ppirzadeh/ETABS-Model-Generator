import pandas as pd
import modelgenerator
import shapely
import numpy as np
from tqdm import tqdm


class Structure:
    """
    Object containing all the necessary information to build a complete ETABS model (starting from Degenkolb template model).
    
    Args:
        df_floors (DataFrame):
            dataframe containing floor information. Each row represents a floor from roof down to base. Headers include:
                "floor_name", "floor_height", "floor_elev", "SD_load", "live_load", "cladding_load", "floor_polygon", "slab", "girder", "beam", "column"
                
        x_grids (dict):
            horizontal grids have numeric labels in str format ('1'-'25'). Key is grid name, value is the Y ordinate
            
        y_grids (dict):
            vertical grids have letter labels ('A'-'Y'). Key is grid name, value is the X ordinate
                
        df_SFRSbays (DataFrame):
            dataframe containing information about where SFRS bays are located. Each row represents a floor from roof down to base. Headers include:
               "floor_name", "bay_1", "bay_2", "bay_3", ...
                
        df_MF (DataFrame):
            dataframe moment frame member section size. Each row represents a floor from roof down to base. Headers include:
                "x_column", "x_beam", "y_column", "y_beam"
                equal to NONE if empty table.
                
        df_braces (DataFrame):
            dataframe brace section size. Each row represents a floor from roof down to base. Headers include:
                "x_brace", "x_config", "y_brace", "y_config"
                equal to NONE if empty table.
                
        df_walls (DataFrame):
            dataframe wall thickness. Each row represents a floor from roof down to base. Headers include:
                "x_wall", "y_wall"
                equal to NONE if empty table.
                
        model_options (dict):
            dictionary containing some default model settings:
                ...["diaphragm_type"] = "Rigid" or "Semi-rigid"
                ...["base_fixity"] = "Fixed" or "Pinned"
                ...["enable_REZ"] = True or False
                ...["n_infill"] = 0 to 4
            
    """
    def __init__(self, df_floors, x_grids, y_grids, df_SFRSbays, df_MF, df_braces, df_walls, model_options):
        # input args
        self.df_floors = df_floors
        self.x_grids = x_grids
        self.y_grids = y_grids
        self.df_SFRSbays = df_SFRSbays
        self.df_MF = df_MF
        self.df_braces = df_braces
        self.df_walls = df_walls
        self.model_options = model_options
        
        # grids and elevations
        self.floor_names = None             # list:: floor names from roof to base
        self.floor_height = None            # list:: floor heights. Indices correspond with self.floor_names
        self.floor_z = None                 # list:: floor elevations from base. Indices correspond with self.floor_names
        
        # floors
        self.floor_objects = None           # dict:: storing all floor objects. Key is the floor_name
        
        # frames
        self.frame_objects = None           # dict:: storing all frame objects. Key is the uniquename of frame
        
        # grouping frames
        self.index_for = None               # dict:: storing list of frame id that's relevant to a group, such as on the same grid line, etc
        self.index_for_walls = None         # dict:: same thing as above. Walls uniquename may overlap with frames so it is stored separately.
        
        
    def init_index_groups(self):
        """
        Initialize keys for self.index_for dictionary. Keys include:
        The index_for dictionary will return a list of uniqueNames that satisfy a given condition.
        """
        # frame members
        self.index_for = dict()
        self.index_for["column"] = []
        self.index_for["girder"] = []
        self.index_for["beam"] = []
        self.index_for["SFRS"] = []
        self.index_for["SFRS_beamX"] = []
        self.index_for["SFRS_beamY"] = []
        self.index_for["SFRS_columnX"] = []
        self.index_for["SFRS_columnY"] = []
        self.index_for["SFRS_braceX"] = []
        self.index_for["SFRS_braceY"] = []
        self.index_for["deleted"] = []
        for floor in self.floor_names:
            self.index_for[f"{floor}"] = []
        for xgrid in self.x_grids.keys():
            self.index_for[f"on {xgrid}"] = []
        for ygrid in self.y_grids.keys():
            self.index_for[f"on {ygrid}"] = []
            
        # area objects can have same uniqueName as frame. Cannot keep in same set
        self.index_for_walls = dict()
        self.index_for_walls["SFRS_wallX"] = []
        self.index_for_walls["SFRS_wallY"] = []
        for floor in self.floor_names:
            self.index_for_walls[f"{floor}"] = []
        for xgrid in self.x_grids.keys():
            self.index_for_walls[f"on {xgrid}"] = []
        for ygrid in self.y_grids.keys():
            self.index_for_walls[f"on {ygrid}"] = []
        
        
        
    def create_grids(self, SapModel):
        """
        ETABS API currently cannot change grids. Need to use interactive database. 
            Grid Definitions - Grid Lines:
                Name = G1
                Grid Line Type = "X (Cartesian)" or "Y (Cartesian)"
                ID = 123... for X direction, ABC... for Y direction
                Ordinate = float value
                *Angle, *X1, *Y1, *X2, *Y2 = Empty
                Bubble Location = "End" or "Start"
                Visible = True or False
        """
        # create a dataframe for csv conversion
        df_dict = {"Name" : [],
                   "Grid Line Type" : [],
                   "ID" : [],
                   "Ordinate" : [],
                   "Angle" : [],
                   "X1" : [],
                   "Y1" : [],
                   "X2" : [],
                   "Y2" : [],
                   "Bubble Location" : [],
                   "Visible" : []}
        for k,v in self.x_grids.items():
            df_dict["Grid Line Type"].append("Y (Cartesian)")
            df_dict["ID"].append(k)
            df_dict["Ordinate"].append(v)
            df_dict["Bubble Location"].append("Start")
            df_dict["Name"].append("G1")
            df_dict["Angle"].append(None)
            df_dict["X1"].append(None)
            df_dict["Y1"].append(None)
            df_dict["X2"].append(None)
            df_dict["Y2"].append(None)
            df_dict["Visible"].append(True)
        for k,v in self.y_grids.items():
            df_dict["Grid Line Type"].append("X (Cartesian)")
            df_dict["ID"].append(k)
            df_dict["Ordinate"].append(v)
            df_dict["Bubble Location"].append("Start")
            df_dict["Name"].append("G1")
            df_dict["Angle"].append(None)
            df_dict["X1"].append(None)
            df_dict["Y1"].append(None)
            df_dict["X2"].append(None)
            df_dict["Y2"].append(None)
            df_dict["Visible"].append(True)
        grids_df = pd.DataFrame(df_dict)
        grids_csv = grids_df.to_csv(index=False)
        
        # push grids to ETABS using interactive database
        table_version, csv_str, ret = SapModel.DatabaseTables.GetTableForEditingCSVString("Grid Definitions - Grid Lines", None)
        ret = SapModel.DatabaseTables.SetTableForEditingCSVString(TableKey = "Grid Definitions - Grid Lines",
                                                                  TableVersion = table_version,
                                                                  csvString = grids_csv)
        
        # must reset grid range for new grid to apply...
        table_version, csv_str, ret = SapModel.DatabaseTables.GetTableForEditingCSVString("Grid Definitions - General", None)
        csv_str_modified = csv_str
        ret = SapModel.DatabaseTables.SetTableForEditingCSVString(TableKey = "Grid Definitions - General",
                                                                  TableVersion = table_version,
                                                                  csvString = csv_str_modified)
        ret = SapModel.DatabaseTables.ApplyEditedTables(True)
        
    
    def create_elevations(self, SapModel):
        """
        Generate story elevation definition using SapModel.Story.SetStories_2
        """
        n_stories = len(self.df_floors)
        self.floor_names = list(self.df_floors["floor_name"])
        self.floor_height = [x*12 for x in list(self.df_floors["floor_height"])]
        self.floor_z = [x*12 for x in list(self.df_floors["floor_elev"])]
        
        # API expects stories to be passed base to roof. need to reversed with [::-1]
        story_names = self.floor_names[::-1] 
        story_height = self.floor_height[::-1]
        
        # inject into ETABS
        ret = SapModel.Story.SetStories_2(BaseElevation = 0,
                                          NumberStories = n_stories,
                                          StoryNames = story_names,
                                          StoryHeights = story_height,
                                          IsMasterStory = [True]*n_stories,
                                          SimilarToStory = ["None"]*n_stories,
                                          SpliceAbove = [False]*n_stories,
                                          SpliceHeight = [0]*n_stories)
        
    
    def create_floors(self, SapModel):
        """
        Create a floor object representation in Python, and then push to ETABS model
        """
        floor_type = "RIGID" if self.model_options["diaphragm_type"]=="Rigid" else "SEMI-RIGID"
        self.floor_objects = dict()
        for i in range(len(self.df_floors)):
            # parse properties
            floor_name = self.df_floors.loc[i, "floor_name"]
            sd_load = self.df_floors.loc[i, "SD_load"] / 1000 / 12 / 12 #ksi
            live_load = self.df_floors.loc[i, "live_load"] / 1000 / 12 / 12 #ksi
            cladding_load = self.df_floors.loc[i, "cladding_load"] / 1000 / 12 #k/in
            section = self.df_floors.loc[i, "slab"]
            z = self.df_floors.loc[i, "floor_elev"] * 12
            
            # parse vertices from str to list of tuples (last point does not repeat first)
            # e.g. "(0,0);(37,0);(37,26);(0,26)" --> remove spaces --> split by ; then for each element:
            # e.g. "(37,0)" --> split by comma --> x coord remove "(" --> y coord remove ")"
            vertices = []
            all_vertices_str = self.df_floors.loc[i, "floor_polygon"]
            all_vertices_str = all_vertices_str.replace(" ","")
            for vertex_str in all_vertices_str.split(";"):
                x_str = vertex_str.split(",")[0]
                x_str = x_str.strip("(")
                y_str = vertex_str.split(",")[1]
                y_str = y_str.strip(")")
                vertices.append((float(x_str), float(y_str)))
            
            # calculate area and perimeter
            floor_polygon = shapely.Polygon(vertices)
            area = floor_polygon.area
            perimeter = floor_polygon.length
            
            # add cladding load (lbs/ft to SDL psf)
            cladding_psf = (cladding_load * perimeter) / area
            
            # create floor objects
            floor_obj = modelgenerator.Floor(story = floor_name, 
                                             diaphragm = floor_type, 
                                             z = z,
                                             vertices = vertices, 
                                             SD_load = sd_load + cladding_psf, 
                                             live_load = live_load, 
                                             section = section)
            # apply properties
            floor_obj.add_by_coord(SapModel)
            floor_obj.set_diaphragm(SapModel)
            floor_obj.set_loading(SapModel)
            self.floor_objects[floor_name] = floor_obj
        
        
    def create_frames(self, SapModel):
        """
        Create frame objects and push them into ETABS model
        """
        # initialize groups to store frame element uids
        self.init_index_groups()
        
        # generate elements floor by floor from roof to base
        frame_list = []
        for idx in tqdm(range(len(self.df_floors))):
            floor_name = self.df_floors.loc[idx, "floor_name"]
            col_section = self.df_floors.loc[idx, "column"]
            girder_section = self.df_floors.loc[idx, "girder"]
            bm_section = self.df_floors.loc[idx, "beam"]
            z_current = self.df_floors.loc[idx, "floor_elev"] * 12
            z_below = z_current - self.df_floors.loc[idx, "floor_height"] * 12
            tqdm.write(f"\t {floor_name}")
            
            # columns
            for ygrid,x in self.y_grids.items():
                for xgrid,y in self.x_grids.items():
                    frame_obj = modelgenerator.Frame(frame_type = "column", 
                                                     story = floor_name, 
                                                     section = col_section, 
                                                     end_coords = [(x,y,z_below), (x,y,z_current)])
                    frame_obj.add_by_coord(SapModel)
                    frame_list.append(frame_obj)
                    self.index_for["column"].append(frame_obj.unique_name)
                    self.index_for[f"{floor_name}"].append(frame_obj.unique_name)
                    self.index_for[f"on {xgrid}"].append(frame_obj.unique_name)
                    self.index_for[f"on {ygrid}"].append(frame_obj.unique_name)
            
            # X girders
            xgrid_items = list(self.x_grids.items())
            ygrid_items = list(self.y_grids.items())
            for i in range(len(xgrid_items)):
                for j in range(len(ygrid_items)-1):
                    xgrid, y = xgrid_items[i]
                    _, x_start = ygrid_items[j]
                    _, x_end = ygrid_items[j+1]
                    frame_obj = modelgenerator.Frame(frame_type = "girder", 
                                                     story = floor_name, 
                                                     section = girder_section, 
                                                     end_coords = [(x_start,y,z_current), (x_end,y,z_current)])
                    frame_obj.add_by_coord(SapModel)
                    frame_obj.set_releases(SapModel, is_pinned=True)
                    frame_obj.set_cardinal_point(SapModel)
                    frame_list.append(frame_obj)
                    self.index_for["girder"].append(frame_obj.unique_name)
                    self.index_for[f"{floor_name}"].append(frame_obj.unique_name)
                    self.index_for[f"on {xgrid}"].append(frame_obj.unique_name)
                    
            # Y girders (size will actually be infill beam)
            for i in range(len(ygrid_items)):
                for j in range(len(xgrid_items)-1):
                    ygrid, x = ygrid_items[i]
                    _, y_start = xgrid_items[j]
                    _, y_end = xgrid_items[j+1]
                    frame_obj = modelgenerator.Frame(frame_type = "beam", 
                                                     story = floor_name, 
                                                     section = bm_section, 
                                                     end_coords = [(x,y_start,z_current), (x,y_end,z_current)])
                    frame_obj.add_by_coord(SapModel)
                    frame_obj.set_releases(SapModel, is_pinned=True)
                    frame_obj.set_cardinal_point(SapModel)
                    frame_list.append(frame_obj)
                    self.index_for["beam"].append(frame_obj.unique_name)
                    self.index_for[f"{floor_name}"].append(frame_obj.unique_name)
                    self.index_for[f"on {ygrid}"].append(frame_obj.unique_name)
            
            # Y infill beams
            for i in range(len(ygrid_items)-1):
                for j in range(len(xgrid_items)-1):
                    for k in range(self.model_options["n_infill"]):
                        _, x_left = ygrid_items[i]
                        _, x_right = ygrid_items[i+1]
                        _, y_start = xgrid_items[j]
                        _, y_end = xgrid_items[j+1]
                        
                        bay_width = x_right - x_left
                        x = x_left + (k+1)*(bay_width) / (self.model_options["n_infill"]+1)
                        
                        frame_obj = modelgenerator.Frame(frame_type = "beam", 
                                                         story = floor_name, 
                                                         section = bm_section, 
                                                         end_coords = [(x,y_start,z_current), (x,y_end,z_current)])
                        frame_obj.add_by_coord(SapModel)
                        frame_obj.set_releases(SapModel, is_pinned=True)
                        frame_obj.set_cardinal_point(SapModel)
                        frame_list.append(frame_obj)
                        self.index_for["beam"].append(frame_obj.unique_name)
                        self.index_for[f"{floor_name}"].append(frame_obj.unique_name)
                        
            SapModel.View.RefreshView()
                        
        # store all frame objects in a dict
        self.frame_objects = dict()
        for frame_obj in frame_list:
            self.frame_objects[frame_obj.unique_name] = frame_obj
   
    
    def delete_frames(self, SapModel):
        """
        Using shapely, delete all elements on each floor that falls outside of slab polygon
        """
        # loop through floors from roof to base (serial run)
        for i in tqdm(range(len(self.floor_names))):
            floor_name = self.floor_names[i]
            tqdm.write(f"\t {floor_name}")
            
            # create floor polygon
            floor_polygon = shapely.Polygon(self.floor_objects[floor_name].vertices)
            shapely.prepare(floor_polygon)
            
            # relevant frame members 
            relevant_idx = self.index_for[floor_name]
            for idx in relevant_idx:
                frame_obj = self.frame_objects[idx]
                vertices = [(a[0],a[1]) for a in frame_obj.end_coords]
                line = shapely.LineString(vertices)
                if not floor_polygon.covers(line):
                    frame_obj.delete(SapModel)
                    self.index_for["deleted"].append(idx)
            SapModel.View.RefreshView()
        
        # remove deleted indices from other groups
        self.index_for["column"] = list(set(self.index_for["column"]) - set(self.index_for["deleted"]))
        self.index_for["girder"] = list(set(self.index_for["girder"]) - set(self.index_for["deleted"]))
        self.index_for["beam"] = list(set(self.index_for["beam"]) - set(self.index_for["deleted"]))
        
        
    def add_SFRS(self, SapModel):
        """
        Add SFRS members based on the df_SFRSbays input table. This method calls three other methods
            self.add_MFs()
            self.add_braces()
            self.add_walls()
        """
        if self.df_MF is not None:
            print("\t Adding moment frames")
            self.add_MFs(SapModel)
            
        if self.df_braces is not None:
            print("\t Adding braces")    
            self.add_braces(SapModel)
        
        if self.df_walls is not None:
            print("\t Adding walls")
            self.add_walls(SapModel)
        
        
    def add_MFs(self, SapModel):
        """
        Add moment frame members. This is a triple nested loop:
            For every level, for every SFRS bay range on that level, and for each member within the bay range
        """
        N_stories = self.df_SFRSbays.shape[0]
        N_bays = self.df_SFRSbays.shape[1]
        
        # loop from each floor from roof to base
        for i in tqdm(range(N_stories)):
            floor_name = self.df_SFRSbays.loc[i, "floor_name"]
            x_bm = self.df_MF.loc[i,"x_beam"]
            x_col = self.df_MF.loc[i,"x_column"]
            y_bm = self.df_MF.loc[i,"y_beam"]
            y_col = self.df_MF.loc[i,"y_column"]
            
            # loop through each SFRS bay entered by user
            for j in range(N_bays-1):
                SFRS_string = self.df_SFRSbays.iloc[i, j+1] # +1 because first col is floor_name
                if not pd.isna(SFRS_string):
                    # parse string (e.g. 1;B-E)
                    grid_on = SFRS_string.split(";")[0]
                    grid_fromto = SFRS_string.split(";")[1]
                    grid_from = grid_fromto.split("-")[0]
                    grid_to = grid_fromto.split("-")[1]
                    
                    # get ordinate limit
                    if grid_from in self.x_grids:
                        ordinates = [self.x_grids[grid_from], self.x_grids[grid_to]]
                        ordinate_from = min(ordinates)
                        ordinate_to = max(ordinates)
                        frame_direction = "Y"
                    else:
                        ordinates = [self.y_grids[grid_from], self.y_grids[grid_to]]
                        ordinate_from = min(ordinates)
                        ordinate_to = max(ordinates)
                        frame_direction = "X"
                    
                    # loop through relevant members and check if they are in SFRS bay
                    relevant_member_id = set(self.index_for[f"on {grid_on}"]) & set(self.index_for[floor_name])
                    for uid in relevant_member_id:
                        frame_obj = self.frame_objects[uid]
                        is_in_bay = frame_obj.check_in_SFRSbay(frame_direction, ordinate_from, ordinate_to)
                        
                        # if in bay, apply SFRS-related changes
                        if is_in_bay:
                            frame_obj.set_releases(SapModel, is_pinned=False)
                            frame_obj.is_lateral = True
                            frame_obj.frame_direction = frame_direction
                            if self.model_options["enable_REZ"]:
                                frame_obj.set_rigid_end_offset(SapModel)
                            self.index_for["SFRS"].append(uid)
                            
                            if frame_direction == "X":
                                if frame_obj.frame_type == "column":
                                    frame_obj.frame_type = "SFRS_column"
                                    frame_obj.change_section(SapModel, x_col)
                                    self.index_for["SFRS_columnX"].append(uid)
                                    
                                elif frame_obj.frame_type == "girder":
                                    frame_obj.frame_type = "SFRS_beam"
                                    frame_obj.change_section(SapModel, x_bm)
                                    self.index_for["SFRS_beamX"].append(uid)
                            
                            elif frame_direction == "Y":
                                if frame_obj.frame_type == "column":
                                    frame_obj.frame_type = "SFRS_column"
                                    frame_obj.change_section(SapModel, y_col)
                                    frame_obj.rotate_axes(SapModel, angle=90)
                                    self.index_for["SFRS_columnY"].append(uid)
                                    
                                elif frame_obj.frame_type == "beam": # y direction girders are bm sized and have type "beam"
                                    frame_obj.frame_type = "SFRS_beam"
                                    frame_obj.change_section(SapModel, y_bm)
                                    self.index_for["SFRS_beamY"].append(uid)
                             
                                
    def add_braces(self, SapModel):
        """
        Add SFRS braces to structure. Algorithm is similar to add_MFs but we are adding
        new members here instead of just changing section size and properties.
        """
        N_stories = self.df_SFRSbays.shape[0]
        N_bays = self.df_SFRSbays.shape[1]
        brace_generator_funcs = dict()
        brace_generator_funcs["SingleA"] = self._add_braces_singleA #/
        brace_generator_funcs["SingleB"] = self._add_braces_singleB #\
        brace_generator_funcs["X"] = self._add_braces_X
        brace_generator_funcs["V"] = self._add_braces_V
        brace_generator_funcs["Chevron"] = self._add_braces_chevron
        
        # loop from each floor from roof to base
        for i in tqdm(range(N_stories)):
            SapModel.View.RefreshView()
            floor_name = self.df_SFRSbays.loc[i, "floor_name"]
            z_current = self.df_floors.loc[i, "floor_elev"] * 12
            z_below = z_current - self.df_floors.loc[i, "floor_height"] * 12
            
            # loop through each SFRS bay entered by user
            for j in range(N_bays-1):
                SFRS_string = self.df_SFRSbays.iloc[i, j+1] # +1 because first col is floor_name
                if not pd.isna(SFRS_string):
                    # parse string (e.g. 1;B-E)
                    grid_on = SFRS_string.split(";")[0]
                    grid_fromto = SFRS_string.split(";")[1]
                    start = grid_fromto.split("-")[0]
                    end = grid_fromto.split("-")[1]
                    
                    # get coordinates and other info required to generation brace frames
                    if grid_on in self.x_grids:
                        frame_direction = "X" #e.g. 1:A-C
                        abscissa = self.x_grids[grid_on]
                        grid_range = [chr(x) for x in range(ord(start), ord(end) +1)]
                        ordinate_range = [self.y_grids[x] for x in grid_range]
                        brace_section = self.df_braces.loc[i,"x_brace"]
                        brace_config = self.df_braces.loc[i,"x_config"]
                    else:
                        frame_direction = "Y" #e.g. A:3-7
                        abscissa = self.y_grids[grid_on]
                        grid_range = [str(x) for x in range(int(start),int(end)+1)]
                        ordinate_range = [self.x_grids[x] for x in grid_range]
                        brace_section = self.df_braces.loc[i,"y_brace"]
                        brace_config = self.df_braces.loc[i,"y_config"]

                    # string parsing is hard with backslash (\), implemented a workaround here
                    if "SingleA" in brace_config:
                        brace_config = "SingleA"
                    if "SingleB" in brace_config:
                        brace_config = "SingleB"
                        
                    # select the correct brace generation function and call it
                    brace_generation_func = brace_generator_funcs[brace_config]
                    brace_generation_func(SapModel = SapModel,
                                          floor_name = floor_name,
                                          direction = frame_direction,
                                          abscissa = abscissa,
                                          ordinate_range = ordinate_range,
                                          brace_section = brace_section,
                                          z_current = z_current,
                                          z_below = z_below,
                                          ongrid = grid_on)
                        
    
    def add_walls(self, SapModel):
        """
        Add wall elements. Algorithm is similar to add_braces except it is simpler, no need
        to have logic for different brace configurations
        """
        N_stories = self.df_SFRSbays.shape[0]
        N_bays = self.df_SFRSbays.shape[1]
        
        # delete piers previously defined
        N_pier, pier_list, ret = SapModel.PierLabel.GetNameList()
        for pier in pier_list:
            if pier != "P1":
                ret = SapModel.PierLabel.Delete(pier)
        
        # loop from each floor from roof to base
        for i in tqdm(range(N_stories)):
            SapModel.View.RefreshView()
            floor_name = self.df_SFRSbays.loc[i, "floor_name"]
            z_current = self.df_floors.loc[i, "floor_elev"] * 12
            z_below = z_current - self.df_floors.loc[i, "floor_height"] * 12
            x_wall = self.df_walls.loc[i,"x_wall"]
            y_wall = self.df_walls.loc[i,"y_wall"]
            
            # loop through each SFRS bay entered by user
            for j in range(N_bays-1):
                SFRS_string = self.df_SFRSbays.iloc[i, j+1] # +1 because first col is floor_name
                if not pd.isna(SFRS_string):
                    # parse string (e.g. 1;B-E)
                    grid_on = SFRS_string.split(";")[0]
                    grid_fromto = SFRS_string.split(";")[1]
                    start = grid_fromto.split("-")[0]
                    end = grid_fromto.split("-")[1]
                    pier_label = floor_name + "_" + SFRS_string
                    
                    # generate walls
                    if grid_on in self.x_grids:
                        wall_direction = "X"
                        abscissa = self.x_grids[grid_on]
                        grid_range = [chr(x) for x in range(ord(start), ord(end) +1)]
                        ordinate_range = [self.y_grids[x] for x in grid_range]
                        
                        for k in range(len(ordinate_range)-1):
                            start = ordinate_range[k]
                            end = ordinate_range[k+1]
                            vertices = [(start, abscissa, z_current),
                                        (end, abscissa, z_current),
                                        (end, abscissa, z_below),
                                        (start, abscissa, z_below)]
                            wall_obj = modelgenerator.Wall(story = floor_name, 
                                                           vertices = vertices, 
                                                           section = x_wall, 
                                                           wall_direction=wall_direction,
                                                           pier_label = pier_label)
                            wall_obj.add_by_coord(SapModel)
                            wall_obj.set_pier_label(SapModel)
                            
                            # add to relevant groups
                            self.index_for_walls[floor_name].append(wall_obj.unique_name)
                            self.index_for_walls[f"on {grid_on}"].append(wall_obj.unique_name)
                            self.index_for_walls["SFRS_wallX"].append(wall_obj.unique_name)
                    else:
                        wall_direction = "Y" #e.g. A:3-7
                        abscissa = self.y_grids[grid_on]
                        grid_range = [str(x) for x in range(int(start),int(end)+1)]
                        ordinate_range = [self.x_grids[x] for x in grid_range]
                        
                        for k in range(len(ordinate_range)-1):
                            start = ordinate_range[k]
                            end = ordinate_range[k+1]
                            vertices = [(abscissa, start, z_current),
                                        (abscissa, end, z_current),
                                        (abscissa, end, z_below),
                                        (abscissa, start, z_below)]
                            wall_obj = modelgenerator.Wall(story = floor_name, 
                                                           vertices = vertices, 
                                                           section = y_wall, 
                                                           wall_direction=wall_direction,
                                                           pier_label = pier_label)
                            wall_obj.add_by_coord(SapModel)
                            wall_obj.set_pier_label(SapModel)
                            
                            # add to relevant groups
                            self.index_for_walls[floor_name].append(wall_obj.unique_name)
                            self.index_for_walls[f"on {grid_on}"].append(wall_obj.unique_name)
                            self.index_for_walls["SFRS_wallY"].append(wall_obj.unique_name)
                        
    
    def set_base_fixity(self, SapModel):
        """Set structural base nodes as fixed or pinned depending on user input"""
        # base is automatically pinned. Only need to execute if user wants fully fixed base
        if self.model_options["base_fixity"] == "Fixed":
            N_nodes, node_names, x, y, z, ret = SapModel.PointObj.GetAllPoints()
            bool_mask = np.array([z]) == 0
            bool_mask = list(bool_mask)[0] # weird np data structure. Convert to simple list
            
            for i in range(len(bool_mask)):
                if bool_mask[i]:
                    SapModel.PointObj.SetRestraint(Name=node_names[i], Value=[True, True, True, True, True, True])
        
        
    def set_groups(self, SapModel):
        """
        Create some groups in ETABS for ease of access:
        """
        group_list = ["SFRS_BM X",
                      "SFRS_BM Y",
                      "SFRS_COL X",
                      "SFRS_COL Y",
                      "SFRS_BRACE X",
                      "SFRS_BRACE Y",
                      "SFRS_WALL X",
                      "SFRS_WALL Y"]
        N_groups, group_names, ret = SapModel.GroupDef.GetNameList()
        
        # delete and recreate groups if they exist already
        for group in group_list:
            if group in group_names:
                ret = SapModel.GroupDef.Delete(group)
                ret = SapModel.GroupDef.SetGroup_1(group)
            else:
                ret = SapModel.GroupDef.SetGroup_1(group)
        
        # main SFRS group
        for uid in self.index_for["SFRS"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "ALL LATERAL")
        for uid in self.index_for_walls["SFRS_wallX"]:
            SapModel.AreaObj.SetGroupAssign(Name = uid, GroupName = "ALL LATERAL")
        for uid in self.index_for_walls["SFRS_wallY"]:
            SapModel.AreaObj.SetGroupAssign(Name = uid, GroupName = "ALL LATERAL")
        
        # Other SFRS groups
        for uid in self.index_for["SFRS_beamX"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_BM X")
        for uid in self.index_for["SFRS_beamY"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_BM Y")
        for uid in self.index_for["SFRS_columnX"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_COL X")
        for uid in self.index_for["SFRS_columnY"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_COL Y")
        for uid in self.index_for["SFRS_braceX"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_BRACE X")
        for uid in self.index_for["SFRS_braceY"]:
            SapModel.FrameObj.SetGroupAssign(Name = uid, GroupName = "SFRS_BRACE Y")
        
        # wall element groups
        for uid in self.index_for_walls["SFRS_wallX"]:
            SapModel.AreaObj.SetGroupAssign(Name = uid, GroupName = "SFRS_WALL X")
        for uid in self.index_for_walls["SFRS_wallX"]:
            SapModel.AreaObj.SetGroupAssign(Name = uid, GroupName = "SFRS_WALL Y")
        
        

    def _add_braces_singleA(self, SapModel, floor_name, direction, abscissa, ordinate_range, brace_section,
                            z_current, z_below, ongrid):
        """Helper method called by self.add_braces()"""
        for k in range(len(ordinate_range)-1):
            start = ordinate_range[k]
            end = ordinate_range[k+1]
            
            if direction == "X":
                end_coords = [(start,  abscissa,   z_below),
                              (end,    abscissa,   z_current)]
                index_group = "SFRS_braceX"
            elif direction == "Y":
                end_coords = [(abscissa,  start,   z_below),
                              (abscissa,    end,   z_current)]
                index_group = "SFRS_braceY"
            
            # add brace and set properties
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords)
            frame_obj.add_by_coord(SapModel)
            frame_obj.set_releases(SapModel, is_pinned=False)
            if self.model_options["enable_REZ"]:
                frame_obj.set_rigid_end_offset(SapModel)
            frame_obj.is_lateral = True
            frame_obj.frame_direction = direction
            
            # add to relevant groups
            self.index_for[floor_name].append(frame_obj.unique_name)
            self.index_for[f"on {ongrid}"].append(frame_obj.unique_name)
            self.index_for["SFRS"].append(frame_obj.unique_name)
            self.index_for[index_group].append(frame_obj.unique_name)
        
        
    def _add_braces_singleB(self, SapModel, floor_name, direction, abscissa, ordinate_range, brace_section,
                            z_current, z_below, ongrid):
        """Helper method called by self.add_braces()"""
        for k in range(len(ordinate_range)-1):
            start = ordinate_range[k+1]
            end = ordinate_range[k]
            
            if direction == "X":
                end_coords = [(start,  abscissa,   z_below),
                              (end,    abscissa,   z_current)]
                index_group = "SFRS_braceX"
            elif direction == "Y":
                end_coords = [(abscissa,  start,   z_below),
                              (abscissa,    end,   z_current)]
                index_group = "SFRS_braceY"
            
            # add brace and set properties
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords)
            frame_obj.add_by_coord(SapModel)
            frame_obj.set_releases(SapModel, is_pinned=False)
            if self.model_options["enable_REZ"]:
                frame_obj.set_rigid_end_offset(SapModel)
            frame_obj.is_lateral = True
            frame_obj.frame_direction = direction
            
            # add to relevant groups
            self.index_for[floor_name].append(frame_obj.unique_name)
            self.index_for[f"on {ongrid}"].append(frame_obj.unique_name)
            self.index_for["SFRS"].append(frame_obj.unique_name)
            self.index_for[index_group].append(frame_obj.unique_name)
        
    
    def _add_braces_V(self, SapModel, floor_name, direction, abscissa, ordinate_range, brace_section,
                            z_current, z_below, ongrid):
        """Helper method called by self.add_braces()"""
        frame_list = []
        for k in range(len(ordinate_range)-1):
            start = ordinate_range[k]
            end = ordinate_range[k+1]
            midpoint = (end + start)/2
            
            if direction == "X":
                end_coords1 = [(start,      abscissa,   z_current),
                              (midpoint,    abscissa,   z_below)]
                
                end_coords2 = [(midpoint,   abscissa,   z_below),
                              (end,         abscissa,   z_current)]
                index_group = "SFRS_braceX"
                
            elif direction == "Y":
                end_coords1 = [(abscissa,   start,      z_current),
                              (abscissa,    midpoint,   z_below)]
                
                end_coords2 = [(abscissa,   midpoint,   z_below),
                              (abscissa,    end,        z_current)]
                index_group = "SFRS_braceY"
            
            # add first brace member
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords1)
            frame_list.append(frame_obj)
            
            # add second brace member
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords2)
            frame_list.append(frame_obj)
        
        # apply SFRS related properties
        for frame in frame_list:
            frame.add_by_coord(SapModel)
            frame.set_releases(SapModel, is_pinned=False)
            if self.model_options["enable_REZ"]:
                frame.set_rigid_end_offset(SapModel)
            frame.is_lateral = True
            frame.frame_direction = direction
            self.index_for[floor_name].append(frame.unique_name)
            self.index_for[f"on {ongrid}"].append(frame.unique_name)
            self.index_for["SFRS"].append(frame.unique_name)
            self.index_for[index_group].append(frame.unique_name)
    
    
    def _add_braces_chevron(self, SapModel, floor_name, direction, abscissa, ordinate_range, brace_section,
                            z_current, z_below, ongrid):
        """Helper method called by self.add_braces()"""
        frame_list = []
        for k in range(len(ordinate_range)-1):
            start = ordinate_range[k]
            end = ordinate_range[k+1]
            midpoint = (end + start)/2
            
            if direction == "X":
                end_coords1 = [(start,      abscissa,   z_below),
                              (midpoint,    abscissa,   z_current)]
                
                end_coords2 = [(midpoint,   abscissa,   z_current),
                              (end,         abscissa,   z_below)]
                index_group = "SFRS_braceX"
                
            elif direction == "Y":
                end_coords1 = [(abscissa,   start,      z_below),
                              (abscissa,    midpoint,   z_current)]
                
                end_coords2 = [(abscissa,   midpoint,   z_current),
                              (abscissa,    end,        z_below)]
                index_group = "SFRS_braceY"
            
            # add first brace member
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords1)
            frame_list.append(frame_obj)

            # add second brace member
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords2)
            frame_list.append(frame_obj)
            
        # apply SFRS related properties
        for frame in frame_list:
            frame.add_by_coord(SapModel)
            frame.set_releases(SapModel, is_pinned=False)
            if self.model_options["enable_REZ"]:
                frame.set_rigid_end_offset(SapModel)
            frame.is_lateral = True
            frame.frame_direction = direction
            self.index_for[floor_name].append(frame.unique_name)
            self.index_for[f"on {ongrid}"].append(frame.unique_name)
            self.index_for["SFRS"].append(frame.unique_name)
            self.index_for[index_group].append(frame.unique_name)
            
    
    def _add_braces_X(self, SapModel, floor_name, direction, abscissa, ordinate_range, brace_section,
                            z_current, z_below, ongrid):
        """Helper method called by self.add_braces()"""
        frame_list = []
        for k in range(len(ordinate_range)-1):
            start = ordinate_range[k]
            end = ordinate_range[k+1]
            midpoint = (end + start)/2
            z_mid = (z_current + z_below)/2
            
            if direction == "X":
                end_coords1 = [(start,      abscissa,   z_below),
                              (midpoint,    abscissa,   z_mid)]
                
                end_coords2 = [(midpoint,   abscissa,   z_mid),
                              (end,         abscissa,   z_current)]
                
                end_coords3 = [(start,      abscissa,   z_current),
                              (midpoint,    abscissa,   z_mid)]
                
                end_coords4 = [(midpoint,   abscissa,   z_mid),
                              (end,         abscissa,   z_below)]
                
                index_group = "SFRS_braceX"
                
            elif direction == "Y":
                end_coords1 = [(abscissa,   start,      z_below),
                              (abscissa,    midpoint,   z_mid)]
                
                end_coords2 = [(abscissa,   midpoint,   z_mid),
                              (abscissa,    end,        z_current)]
                
                end_coords3 = [(abscissa,   start,      z_current),
                              (abscissa,    midpoint,   z_mid)]
                
                end_coords4 = [(abscissa,   midpoint,   z_mid),
                              (abscissa,    end,        z_below)]
                index_group = "SFRS_braceY"
            
            # add brace members
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords1)
            frame_list.append(frame_obj)
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords2)
            frame_list.append(frame_obj)
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords3)
            frame_list.append(frame_obj)
            frame_obj = modelgenerator.Frame(frame_type = "SFRS_brace", 
                                             story = floor_name, 
                                             section = brace_section, 
                                             end_coords = end_coords4)
            frame_list.append(frame_obj)
            
        # apply SFRS related properties
        for frame in frame_list:
            frame.add_by_coord(SapModel)
            frame.set_releases(SapModel, is_pinned=False)
            if self.model_options["enable_REZ"]:
                frame.set_rigid_end_offset(SapModel)
            frame.is_lateral = True
            frame.frame_direction = direction
            self.index_for[floor_name].append(frame.unique_name)
            self.index_for[f"on {ongrid}"].append(frame.unique_name)
            self.index_for["SFRS"].append(frame.unique_name)
            self.index_for[index_group].append(frame.unique_name)
                    
                    
        