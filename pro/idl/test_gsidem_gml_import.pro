;
;
;
pro test_gsidem_gml_import
  compile_opt idl2
  
  cd, file_dirname(routine_filepath())
  
  e = envi(/HEADLESS)
  if obj_valid(e) ne 1 then begin
    e=envi(/HEADLESS)
  endif
  
  odem = gsidem_gml_import() ; for 5m DEM
  ;odem = obj_new('gsidem_gml_import', /MESH_10, /DUMMY0) ;; for 10m DEM replacing 0 with -9999.00
  ;odem = obj_new('gsidem_gml_import', /MESH_10) ; for 10m DEM
  if obj_valid(odem) ne 1 then message, 'object is not valid'

  indir = '/Users/fogushi/Documents/Develop/gsidem/data/debug'
  ofile = e.getTemporaryFilename(/cleanup_on_exit)
  otiff = '/Users/fogushi/Desktop/test.tif'

  ;indir = 'E:\GSIDEM\data\fujibashi\5m\xml'
  ;indir = dialog_pickfile(/DIRECTORY)
  ;ofile = 'E:\GSIDEM\data\fujibashi\5m\envi\fujibashi_gsi5m_envi.dat'
  ;
  res = odem.import(indir)
  res = odem.mosaic(ofile)
  if res then print, 'mosaic success'

  oras=e.openraster(ofile)
  oras.export, otiff, 'TIFF'

  ;if res then print, 'success' else print, 'failed'
  e.close
  obj_destroy, odem

  print, 'test completed'

end