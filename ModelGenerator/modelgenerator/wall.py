
class Wall:
    """
    Object representation of a wall in ETABS
    
    Args:
        story                           str:: story where this area object belongs to
        vertices                        list:: vertices list of (x,y,z) tuples. Last coord does not repeat first. (inches)
        section                         str:: wall section assignment
        wall_direction                  str:: "X" or "Y"
        pier_label                      str:: assigned pier label
    """
    def __init__(self, story, vertices, section, wall_direction, pier_label):
        # input args
        self.story = story
        self.vertices = vertices
        self.section = section
        self.wall_direction = wall_direction
        self.pier_label = pier_label
        self.unique_name = None             # str:: uid per ETABS. Assigned in add_by_coord()
        
        
    def add_by_coord(self, SapModel):
        """Add floor object to ETABS model"""
        ret = SapModel.AreaObj.AddByCoord(NumberPoints = 4,
                                          X = [xyz[0] for xyz in self.vertices],
                                          Y = [xyz[1] for xyz in self.vertices],
                                          Z = [xyz[2] for xyz in self.vertices],
                                          PropName = self.section)
        self.unique_name = ret[3]
        if ret[-1] != 0:
            print(f"WARNING: failed to add wall shell: {self.unique_name} on {self.story}")
            
    def set_pier_label(self, SapModel):
        """Add this wall shell to pier group"""
        ret = SapModel.PierLabel.SetPier(self.pier_label)
        ret = SapModel.AreaObj.SetPier(Name = self.unique_name,
                                       PierName = self.pier_label)
        if ret != 0:
            print(f"WARNING: could not add wall shell ({self.unique_name})")
            
        