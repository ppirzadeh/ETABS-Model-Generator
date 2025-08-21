
class Frame:
    """
    Object representation of a frame object in ETABS. (beams, columns, braces)
    
    Args:
        frame_type          str:: column, girder, beam, SFRS_beam, SFRS_column, SFRS_brace
        story               str:: story where this frame object belongs to
        section             str:: frame section assignment
        end_coords          list:: xyz tuple of the end coordinates
    """
    def __init__(self, frame_type, story, section, end_coords):
        # input args
        self.frame_type = frame_type
        self.story = story
        self.section = section
        self.end_coords = end_coords
        
        # other frame attributes (determined later)
        self.unique_name = None                 # str:: uid Assigned when added to ETABS in add_by_coord()
        self.deleted = None                     # bool:: true if this member no longer exists in the ETABS model
        self.is_lateral = None                  # bool:: true if frame is a lateral element
        self.frame_direction = None             # str:: "X" or "Y" if a lateral member. Else None
        
        
    def add_by_coord(self, SapModel):
        """Add frame to ETABS by the end coords"""
        ret = SapModel.FrameObj.AddByCoord(XI = self.end_coords[0][0],
                                           YI = self.end_coords[0][1],
                                           ZI = self.end_coords[0][2],
                                           XJ = self.end_coords[1][0],
                                           YJ = self.end_coords[1][1],
                                           ZJ = self.end_coords[1][2],
                                           PropName = self.section)
        self.unique_name = ret[0]
        if ret[-1] != 0:
            print(f"WARNING: failed to add frame with end coord: {self.end_coords}")
        
        
    def set_releases(self, SapModel, is_pinned):
        """Set end releases"""
        if is_pinned:
            II = [False, False, False, True, True, True]
            JJ = [False, False, False, False, True, True]
        else:
            II = [False, False, False, False, False, False]
            JJ = [False, False, False, False, False, False]
            
        ret = SapModel.FrameObj.SetReleases(Name = self.unique_name,
                                            II = II,
                                            JJ = JJ,
                                            StartValue = [0,0,0,0,0,0],
                                            EndValue = [0,0,0,0,0,0])
        
        # NOTE some BRB elements will automatically be released by ETABS after analysis
        if ret[-1] != 0:
            print(f"WARNING: failed to add frame releases for frame: {self.unique_name}")
        
        
    def set_cardinal_point(self, SapModel, cardinal_pt=8):
        """Set insertion point. ETABS default for beams is 8 - top center. Only called for beams"""
        ret = SapModel.FrameObj.SetInsertionPoint_1(Name = self.unique_name,
                                                    CardinalPoint = cardinal_pt,
                                                    Mirror2 = False,
                                                    Mirror3 = False,
                                                    StiffTransform = False,
                                                    Offset1 = [0,0,0],
                                                    Offset2 = [0,0,0])
        if ret[-1] != 0:
            print(f"WARNING: failed to set insertion point for frame: {self.unique_name}")
    
    
    def delete(self, SapModel):
        """Remove itself from the model"""
        ret = SapModel.FrameObj.Delete(self.unique_name)
        self.deleted = True
        
        if ret != 0:
            print(f"WARNING: Could not find and delete frame: {self.unique_name}")
        
         
    def set_rigid_end_offset(self, SapModel):
        """Set member rigid end offset (usually only for lateral members)"""
        # NOTE API QUIRK: need to set AutoOffset to False to ingest RZ = 1. Then set it to True again
        ret = SapModel.FrameObj.SetEndLengthOffset(Name = self.unique_name,
                                                   AutoOffset = False,
                                                   Length1 = 0,
                                                   Length2 = 0,
                                                   RZ = 1,
                                                   ItemType = 0)
        ret = SapModel.FrameObj.SetEndLengthOffset(Name = self.unique_name,
                                                   AutoOffset = True,
                                                   Length1 = 0,
                                                   Length2 = 0,
                                                   RZ = 1,
                                                   ItemType = 0)
        if ret != 0:
            print(f"WARNING: could not set rigid end zone factor for frame: {self.unique_name}")
    
    
    def rotate_axes(self, SapModel, angle):
        """Rotate local axis of frame member. Likely called for columns to align with X or Y direction"""
        ret = SapModel.FrameObj.SetLocalAxes(Name = self.unique_name,
                                             Ang = angle,
                                             ItemType = 0)
        if ret != 0:
            print(f"WARNING: could not rotate local axes for frame: {self.unique_name}")
    
    
    def change_section(self, SapModel, section):
        """Mostly used to change to SFRS section"""
        ret = SapModel.FrameObj.SetSection(Name = self.unique_name,
                                           PropName = section)
        if ret != 0:
            print(f"WARNING: could not change section for frame: {self.unique_name}")
    
    
    def check_in_SFRSbay(self, frame_direction, ordinate_from, ordinate_to):
        """
        Check if this frame is in SFRS bay given a start-end ordinate and a frame direction
        """
        if frame_direction == "X":
            i_inbay = self.end_coords[0][0]>=ordinate_from and self.end_coords[0][0]<=ordinate_to
            j_inbay = self.end_coords[1][0]>=ordinate_from and self.end_coords[1][0]<=ordinate_to
        else:
            i_inbay = self.end_coords[0][1]>=ordinate_from and self.end_coords[0][1]<=ordinate_to
            j_inbay = self.end_coords[1][1]>=ordinate_from and self.end_coords[1][1]<=ordinate_to
            
        inbay = i_inbay and j_inbay
        return inbay
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    