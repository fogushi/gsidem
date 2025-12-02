pro _convert_geoid_to_ellipsoid, infile




end
;
;
;
pro convert_gsidem_gml_to_tiff, INDIR=indir, OUT_TIFF=out_tiff, MESH_10=mesh_10, DUMMUY0=dummy0
  
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

  res = odem.import(indir)
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

<<<<<<< HEAD
  indir = 'E:\tp_proc\gsidem\data\erimo\10m\xml'
  out_tiff = 'E:\tp_proc\gsidem\data\erimo\10m\sarscape\erimo_gsidem10.tif'
  
  convert_gsidem_gml_to_tiff, INDIR=indir, OUT_TIFF=out_tiff, MESH_10=mesh_10, DUMMUY0=dummy0
=======
  indir = 'E:\GSIDEM\data\fujibashi\5m\xml'
  ;indir = dialog_pickfile(/DIRECTORY)
  out_tiff = 'E:\GSIDEM\data\fujibashi\5m\envi\fujibashi_gsi5m_envi.dat'
  ;
  convert_gsidem_gml_to_tiff, INDIR=indir, OUT_TIFF=out_tiff, MESH_10=mesh_10, DUMMUY0=dummy0

>>>>>>> 74630b8e594fb1a6f0dc0846f43733d240f3b3e0

end