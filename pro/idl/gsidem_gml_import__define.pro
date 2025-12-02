;
; import GSI-DEM 10m and 5m
; windows only
;
function gsidem_gml_xml_filter, oNode
  name = oNode.getNodeName()
  if (name eq 'type') or (name eq 'mesh') or (name eq 'gml:lowerCorner') $
    or (name eq 'gml:upperCorner') or (name eq 'gml:high') or (name eq 'gml:low') or $
    (name eq 'gml:tupleList') or (name eq 'gml:startPoint') then return, 1 ; accept
  
  return, 3 ;; skip
  
end
;
;
;
function gsidem_gml_import::init, indir, MESH_10 = mesh_10 , DUMMY0=dummy0

  res = self.idl_object::init()
  if ~res then message, 'faild to initialize idl_object'
  self.member = hash()
  if n_elements(indir) eq 1 then begin
    (self.member)['indir'] = indir
  endif
  
  (self.member)['dummy_flg'] = 0
  (self.member)['mesh_flg'] = 5
  if keyword_set(mesh_10) then (self.member)['mesh_flg'] = 10
  if keyword_set(dummy0) then (self.member)['dummy_flg'] = 1 
  
  e = envi(/CURRENT)
  if ~obj_valid(e) then begin
    return, 0
  endif else begin
    (self.member)['envi'] = e 
    (self.member)['oListRaster'] = list()
  endelse

  return, 1

end
;
;;
;
pro gsi_dem_import::cleanup

  if obj_valid(self.member['oListRaster']) then begin
    oListRaster = self.member['oListRaster']
    oArr = oListRaster.toArray()
    foreach elem, oArr do elem.close
  endif

end 
;
;
;
function gsidem_gml_import::mosaic, ofile, TIFF=tiff
compile_opt idl2
  
  e=envi(/HEADLESS)
  oListRaster = self.member['oListRaster']
  print, 'number of scenes for mosaic: ', oListRaster.length
   
  if oListRaster.length gt 0 then begin
    print, 'Mosaic starts'
    oArr = oListRaster.toArray()
    mosaicRaster = ENVIMosaicRaster(oArr)
    if keyword_set(tiff) then begin
      mosaicRaster.Export, ofile, 'TIFF'
    endif else begin
      mosaicRaster.Export, ofile, 'ENVI'
    endelse
  endif else begin
    return, 0
  endelse
  
  return, 1
  
end
;
;
;
function gsidem_gml_import::import, indir, DUMMY0=dummy0
compile_opt idl2

  if indir eq !null then begin
    indir = envi_pickfile(/DIRECTORY)
    if indir eq '' then begin
      message, "please specify input directory"
      return, 0
    endif
  endif
  
  case (self.member)['mesh_flg'] of
    5: begin
      filelist = file_search(indir + path_sep()+'*5*.xml', COUNT=fcnt)
      ;filelist = file_search(indir + path_sep()+'*5A*.xml', COUNT=fcnt)
      if fcnt lt 1 then begin
        message, 'file is not found', LEVEL=-1
        return, 0
      endif
    end
    10:begin
      filelist = file_search(indir + path_sep(), '*10b*.xml', COUNT=fcnt)
      print, filelist
      ;filelist = file_search(indir + path_sep()+'*10b*.xml', COUNT=fcnt)
      if fcnt lt 1 then begin
        message, 'file is not found', LEVEL=-1
        return, 0
      endif      
    end
    else:begin
      message, 'no mesh type', LEVEL=-1
      return, 0
    end
  endcase
  ;
  ; import
  foreach elem, filelist do begin
    print, "importing ...", elem
    res = self.import_single(elem)
    if res then print, 'import success'
  endforeach
  
  return, 1

end
;
;
;
function gsidem_gml_import::import_single, infile, ofile
  oDoc = obj_new( 'IDLffXMLDOMDocument', FILENAME=infile)
  oNodeIterator = oDoc.createNodeIterator(obj_new(), FILTER_NAME='gsidem_gml_xml_filter' )
  oNode = oNodeIterator->nextNode()
  
  xstart = !null
  ystart = !null

  ret = strmatch(infile, '*10b*.xml')
  if ret eq 1 then begin
    (self.member)['mesh_flg'] = 10
  endif
  
  while obj_valid(oNode) do begin
    ; Assuming only one text node per element
    name = oNode.getNodeName()
    val = (oNode->GetFirstChild())->getNodeValue()
    case name of 
      'type':begin
          print, 'importing...', val
        end
      'mesh':begin
          print, 'mesh number: ', val
        end
      'gml:low':begin
        lowarr = strsplit(val, string(32B), /EXTRACT)
        low_x = fix(lowarr[0])
        low_y = fix(lowarr[1])
        end
      'gml:high':begin
        higharr = strsplit(val, string(32B), /EXTRACT)
        high_x = fix(higharr[0])
        high_y = fix(higharr[1])      
        end
      'gml:lowerCorner':begin
        lrarr =  strsplit(val, string(32B), /EXTRACT)
        print, 'lowerCorner', lrarr
        leftlow_lat = double(lrarr[0])
        leftlow_lon = double(lrarr[1])
        end
      'gml:upperCorner':begin
        ularr =  strsplit(val, string(32B), /EXTRACT)
        print, 'upperCorner', ularr
        rightup_lat = double(ularr[0])
        rightup_lon = double(ularr[1])
        end
      'gml:tupleList':begin
        ;print, name
        valarr = strsplit(val, string(10B), /EXTRACT, COUNT=cntval)
        xsize = high_x - low_x +1LL
        ysize = high_y - low_y + 1LL
        fval = !null
        farr = fltarr(xsize, ysize) ;- 9999.
        ;
        ; modified 2017/03/30
        ; 5m mesh
        case (self.member)['mesh_flg'] of 
          5 :begin
            foreach elem, valarr do begin
              tmpval = strsplit(elem, ',', /EXTRACT)
              fval = [fval, float(tmpval[1])]
            endforeach
          end
          10:begin
            ;for i = 0l, (xsize*ysize)-1 do begin
            for i = 0l, n_elements(valarr)-1 do begin
              if valarr[i] eq ' ' then begin
                 if ((self.member)['dummy_flg'] eq 1) then begin
                    farr[i] = 0.0
                 endif else begin
                    farr[i] = -9999.
                 endelse
                ;farr[i] = 0.0
              endif else begin
                tmpval = strsplit(valarr[i], ',', /EXTRACT)
                if ((self.member)['dummy_flg'] eq 1) then begin
                  if tmpval[1] eq '-9999.00' then begin
                    farr[i] = 0.0
                  endif else begin
                    farr[i] = float(tmpval[1])
                  endelse
                endif else begin
                  farr[i] = float(tmpval[1])
                endelse
              endelse
            endfor
          end
          else:begin
            message, 'no mesh type', LEVEL=-1
            return, 0
          end  
        endcase
        
        ;farr = fltarr(xsize, ysize)-9999.
        ;for i=0ll, cntval-1 do begin
          ;if valarr[i] eq ' ' then begin
          ;  farr[i] = -9999.
          ;endif else begin
          ;  tmpval = strsplit(valarr[i], ',', /EXTRACT)
          ;  farr[i] = float(tmpval[1])
          ;endelse
;          if tmpval[1] eq '-9999.' then begin
;            farr[i] = !values.f_nan
;            continue
;          endif else begin
;            farr[i] = float(tmpval[1])
;          endelse
        ;endfor
        end
      'gml:startPoint':begin
        startarr =  strsplit(val, string(32B), /EXTRACT)
        xstart = long(startarr[0])
        ystart = long(startarr[1])
        end
      else: begin
        print, 'no match'
        print, name
        print, val
        end  
    endcase
    oNode = oNodeIterator->nextNode()
  endwhile
  ;
  ; make raster for 5m DEM
  ;
  if  (self.member)['mesh_flg'] eq 5 then begin
    if (xstart ne !null) or (ystart ne !null) then begin
      nskip = (ystart*xsize)+xstart
      farr[nskip:nskip+n_elements(fval)-1] = fval
    endif else begin
      farr[*] = fval
    endelse
  end 
  
  ;
  ; create an envi format file
  ;
  e = (self.member)['envi']
  
  x_pix_size = abs(rightup_lon - leftlow_lon)/xsize
  y_pix_size = abs(rightup_lat - leftlow_lat)/ysize
  
  jgd2000 = 4326 ;wgs-84
  ;jgd2000 = 4612
  spatialRef1 = e.CreateRasterSpatialRef('standard', $
    COORD_SYS_CODE=jgd2000, /GEOGCS, $
    PIXEL_SIZE=[x_pix_size, y_pix_size], TIE_POINT_PIXEL=[0.0D,0.0D], $
    ;PIXEL_SIZE=[x_pix_size, y_pix_size], TIE_POINT_PIXEL=[0.5D,0.5D], $
    TIE_POINT_MAP=[leftlow_lon, rightup_lat])
   
  if ofile eq !null then begin
   ;ofile = file_dirname(infile) + path_sep() + file_basename(infile, '.xml') + '.dat'
   ofile = e.GetTemporaryFilename()
  endif 

  if ((self.member)['dummy_flg'] eq 1) then begin
    newRaster = e.CreateRaster(ofile, farr, DATA_TYPE=4, NBANDS=1, $
      DATA_IGNORE_VALUE=0.0, SPATIALREF=spatialRef1)
  endif else begin
    newRaster = e.CreateRaster(ofile, farr, DATA_TYPE=4, NBANDS=1, $
      DATA_IGNORE_VALUE=-9999.0, SPATIALREF=spatialRef1)
  endelse
  newRaster.Save
  
  oListRaster = self.member['oListRaster']
  oListRaster.Add, newRaster
  DataColl = e.Data
  DataColl.remove, newRaster
  
;  newRaster.close
;  obj_destroy, newRaster

  obj_destroy, oDoc
  return, 1

end
;
;
;
function gsidem_gml_import::delete_tempfiles
compile_opt IDL2
  
  oListRaster = self.member['oListRaster']
  for cnt=0, oListRaster.length-1 do begin
    filepath = oListRaster[cnt].URI
    oListRaster[cnt].close
    filebase = file_basename(filepath)
    filename = strmid(filebase, 0, strpos(filebase, '.'))
    file = file_search(file_dirname(filepath), '*'+filename+'*')
    for delcnt=0, n_elements(file)-1 do file_delete, file[delcnt], /QUIET
  endfor
  return, 0
end
;
;
;
pro gsidem_gml_import__define
compile_opt idl2

  void = {gsidem_gml_import, $
    inherits idl_object, $
    member:obj_new()}

end
