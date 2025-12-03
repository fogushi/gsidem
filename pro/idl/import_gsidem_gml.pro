;+
; 
;-
pro convert_geotiff_dem_to_ellipsoid, in_tiff
  compile_opt idl2

  out_geoid_file = file_dirname(in_tiff) + path_sep()+ file_basename(in_tiff,'.tif')+'_geoid_dem'
  ;
  ; Initialize ENVI
  e=envi(/HEADLESS)
  if ~obj_valid(e) then message, 'ENVI should be initialized'
  ;
  ; Initialize SARscape
  res = sarscape_core_essentials(/EXT_ONLY_SARMAP_CORE)
  
  ;++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
   module_to_call = 'ImportTiff'
   OB = obj_new('SARscapeBatch',Module=module_to_call)
   IF (~OBJ_VALID(OB)) THEN BEGIN
      message, 'Create object fail : '+module_to_call
   ENDIF
   
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.SARSCAPEENVIRONMENT' , 'IDL_ENVI_ENV'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.INPUT_FILE_LIST' , in_tiff
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.OUTPUT_FILE_LIST' , out_geoid_file
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.TIF_SCALE_FACTOR_VAL' , '1.0000000'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.IS_GEOCODED_VAL' , 'OK'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.DATA_UNITS' , 'GEOIDAL DEM'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.GEOID_TYPE' , 'EGM96'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.USE_DUMMY_FOUND_IN_INPUT_IMAGE_FLAG' , 'OK'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.IS_DUMMY_VAL' , 'NaN'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.COMPLEX_BIP_IF_PAIR_BANDS_FLAG' , 'NotOK'
   OB->SetParam , 'MAIN_BASIC_IMPORT_TIFF_CMD.MAKE_ONLY_AUXILIARIES_FLAG' , 'NotOK'

   ; Verify the parameters
   ok = OB->VerifyParams(Silent=0)
   IF ~ok THEN BEGIN
      message, 'Module can not be executed; Some parameters need to be filled  ['+module_to_call+'] FAIL!'
   ENDIF
  
   ; Process execution
  OK = OB->Execute();
  IF OK THEN BEGIN
    print, 'Success execution ['+module_to_call+'] !'
  ENDIF else begin
    aErrCode = ''
    aOutMsg = get_SARscape_error_string('NotOK',ERROR_CODE=aErrCode)
    aOutMsg = get_SARscape_error_string('OK',ERROR_CODE=aErrCode)
    message, 'FAIL Execution ['+module_to_call+'] EC ['+aErrCode+'] : ['+aOutMsg+']'
  ENDELSE

  ;++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
   module_to_call = 'ToolsGEOID'
   OB = obj_new('SARscapeBatch',Module=module_to_call)
   IF (~OBJ_VALID(OB)) THEN BEGIN
      message, 'Create object fail : '+module_to_call
   ENDIF

   out_ellips_file = file_dirname(in_tiff) + path_sep()+ file_basename(in_tiff,'.tif')+'_ellips_dem'

   OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.SARSCAPEENVIRONMENT' , 'IDL_ENVI_ENV'
   OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.INPUT_FILE_NAME' , out_geoid_file
   OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.OUTPUT_FILE_NAME' , out_ellips_file
   OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.GEOID_OPERATION' , 'subtract'
   OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.GEOID_TYPE' , 'EGM96'
   ;OB->SetParam , 'MAIN_TOOLS_GEOID_CMD.GEOID_FILE_NAME' , 'USER_OPTIONAL_PARAMETER'

   ; Verify the parameters
   ok = OB->VerifyParams(Silent=0)
   IF ~ok THEN BEGIN
      message, 'Module can not be executed; Some parameters need to be filled  ['+module_to_call+'] FAIL!'
   ENDIF
   ; Process execution
   OK = OB->Execute();
   IF OK THEN BEGIN
     print, 'Success execution ['+module_to_call+'] !'
   ENDIF else begin
     aErrCode = ''
     aOutMsg = get_SARscape_error_string('NotOK',ERROR_CODE=aErrCode)
     aOutMsg = get_SARscape_error_string('OK',ERROR_CODE=aErrCode)
     message, 'FAIL Execution ['+module_to_call+'] EC ['+aErrCode+'] : ['+aOutMsg+']'
   ENDELSE

end
;
;
;
pro convert_gsidem_gml_to_tiff, IN_DIR=in_dir, OUT_TIFF=out_tiff, MESH_10=mesh_10, DUMMUY0=dummy0
  
  cd, file_dirname(routine_filepath())
  
  e = envi(/HEADLESS)
  if obj_valid(e) ne 1 then begin
    e=envi(/HEADLESS)
  endif
  
  if keyword_set(mesh_10) then begin
    if keyword_set(dummy0) then begin
        odem=obj_new('gsidem_gml_import', /MESH_10, /DUMMY0) ;
    endif else begin
        odem=obj_new('gsidem_gml_import', /MESH_10)
    endelse
  end else begin
    if keyword_set(dummy0) then begin
      odem = gsidem_gml_import(/DUMMY0) ; for 5m DEM
    endif else begin
      odem = gsidem_gml_import() ; for 5m DEM
    endelse
  endelse

  if obj_valid(odem) ne 1 then message, 'object is not valid'
  tmpfile = e.getTemporaryFilename(/cleanup_on_exit)

  res = odem.import(in_dir)
  res = odem.mosaic(tmpfile)
  if res then print, 'mosaic success'

  oras=e.openraster(tmpfile)
  oras.export, out_tiff, 'TIFF'

  ;if res then print, 'success' else print, 'failed'
  e.close
  obj_destroy, odem

  print, 'test completed'

end
;
; 
;
pro import_gsidem_gml

  in_dir = 'E:\tp_proc\gsidem\data\erimo\10m\xml'
  ;indir = dialog_pickfile(/DIRECTORY)
  out_tiff = 'E:\tp_proc\gsidem\data\erimo\10m\sarscape\erimo_gsidem.tif'
  ;
  convert_gsidem_gml_to_tiff, IN_DIR=in_dir, OUT_TIFF=out_tiff, /MESH_10, /DUMMUY0
  ;+
  ; for SARscape process
  convert_geotiff_dem_to_ellipsoid, out_tiff

  print, 'import completed'

end