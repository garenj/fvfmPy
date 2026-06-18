# Generate script to convert .pim file to .tif files
library(tidyverse)

# Set working directory to where the .pim files are saved
setwd("/Users/u1058369/Library/CloudStorage/Dropbox/Pieter/ANU/ATLS project/Snowgum TLS/20260204")

unlink("script.prg")

# Read filenames
fns_pim = list.files()

# Generate list of .tif filenames
fns_tif = fns_pim %>% str_replace("pim", "tif")


# Remove .pim from filenames because ImagingWin doesn't like it for some god forsaken reason
fns_pim = fns_pim %>% str_remove(".pim")

write_lines("-- Program Start -- |","script.prg")

for(i in 1:length(fns_pim)) {

  pim_line = paste("Load Pim File = |", fns_pim[i], sep="")
  write_lines(pim_line,"script.prg", append = T)

  tif_line = paste("Export to Tiff File = |", fns_tif[i], sep="")
  write_lines(tif_line,"script.prg", append = T)

}


