
class Floor:
    """
    Object representation of a floor in ETABS
    
    Args:
        story                           str:: story where this area object belongs to
        diaphragm                       str:: diaphragm assignment
        z                               float:: z coordinate of the floor plane (inches)
        vertices                        list:: vertices list of (x,y) tuples. Last coord does not repeat first. (inches)
        SD_load                         float:: superimposed dead load (ksi)
        live_load                       float:: live load (ksi)
        section                         str:: floor section assignment
    """
    def __init__(self, story, diaphragm, z, vertices, SD_load, live_load, section):
        # input args
        self.story = story
        self.diaphragm = diaphragm
        self.z = float(z)
        self.vertices = vertices
        self.SD_load = float(SD_load)
        self.live_load = float(live_load)
        self.section = section
        
        self.N_vertices = len(vertices)     # float:: number of vertices
        self.unique_name = None             # str:: uid per ETABS. Assigned in add_by_coord()
        
        
    def add_by_coord(self, SapModel):
        """Add floor object to ETABS model"""
        ret = SapModel.AreaObj.AddByCoord(NumberPoints = self.N_vertices,
                                          X = [xy[0] for xy in self.vertices],
                                          Y = [xy[1] for xy in self.vertices],
                                          Z = [self.z] * self.N_vertices,
                                          PropName = self.section)
        self.unique_name = ret[3]
        if ret[-1] != 0:
            print(f"WARNING: failed to add floor: {self.story}")
        
        
    def set_diaphragm(self, SapModel):
        """ Set diaphragm section"""
        ret = SapModel.AreaObj.SetDiaphragm(Name = self.unique_name,
                                            DiaphragmName = self.diaphragm)
        if ret != 0:
            print(f"WARNING: failed to set diaphragm for floor: {self.story}")
    
    
    def set_loading(self, SapModel):
        """Set floor loading"""
        # superimposed dead load (Dir=10 is gravity direction)
        ret = SapModel.AreaObj.SetLoadUniform(Name = self.unique_name,
                                              LoadPat = "Dead (Superimposed)",
                                              Value = self.SD_load,
                                              Dir = 10)
        if ret != 0:
            print(f"WARNING: failed to set SD load for floor: {self.story}")
            
        # live load
        ret = SapModel.AreaObj.SetLoadUniform(Name = self.unique_name,
                                              LoadPat = "Live",
                                              Value = self.live_load,
                                              Dir = 10)
        if ret != 0:
            print(f"WARNING: failed to set live load for floor: {self.story}")
        