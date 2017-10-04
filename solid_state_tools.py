from __future__ import division
import numpy as np
import re
import periodictable as pt
import sys

bohr = 0.52917721067

# from CifFile import ReadCif
cov_radii = np.loadtxt('./data/cov_radii.dat')/bohr

p_table = {i: el.__repr__() for i, el in enumerate(pt.elements)}
p_table_rev = {el.__repr__(): i for i, el in enumerate(pt.elements)}


class MolecularStructure(object):
    def __init__(self, atoms,scale=1.0):
        self.atoms = np.array(atoms,dtype=np.float) # np array with [x,y,z,type] type is number in periodic system
        self.atoms[:,:3] = self.atoms[:,:3]*scale
        self.n_atoms = atoms.shape[0]
        self.scale = scale  # This is just bonus info. Do not use this here. Only for editing

    def calc_absolute_coordinates(self,repeat=[1,1,1]):
        return self.atoms

    def find_bonds(self,abs_coords):
        n_atoms = abs_coords.shape[0]
        abs_coords_pure = abs_coords[:,:3]

        dist_mat = np.zeros((n_atoms,n_atoms))
        bonds = []
        for j1 in range(n_atoms):
            for j2 in range(j1+1,n_atoms):

                dist = np.linalg.norm(abs_coords_pure[j1,:]-abs_coords_pure[j2,:] )
                if dist < (cov_radii[int(abs_coords[j1,3])]+cov_radii[int(abs_coords[j2,3])])*1.3:
                    dist_mat[j1, j2] = dist
                    bonds.append([j1,j2]);
        return bonds

class CrystalStructure(object):

    def __init__(self,lattice_vectors,atoms,relative_coords=True,scale=1.0):
        self.lattice_vectors = np.array(lattice_vectors,dtype=np.float) # tuple of np.arrays
        volume = np.dot(np.cross(self.lattice_vectors[0,:],self.lattice_vectors[1,:]),self.lattice_vectors[2,:])
        self.inv_lattice_vectors = np.zeros((3,3))
        self.inv_lattice_vectors[0,:] = np.cross(self.lattice_vectors[1,:],self.lattice_vectors[2,:])*2*np.pi/volume
        self.inv_lattice_vectors[1,:] = np.cross(self.lattice_vectors[2,:],self.lattice_vectors[0,:])*2*np.pi/volume
        self.inv_lattice_vectors[2,:] = np.cross(self.lattice_vectors[0,:],self.lattice_vectors[1,:])*2*np.pi/volume

        self.atoms = np.array(atoms,dtype=np.float) # np array with [x,y,z,type] type is number in periodic system
        self.n_atoms = atoms.shape[0]
        self.scale = scale  # This is just bonus info. Do not use this here. Only for editing

        if relative_coords:
            self.atoms[:,:3] = np.mod(self.atoms[:,:3],1)
        else:
            inv_lattice_vecs = np.linalg.inv(self.lattice_vectors.T)
            for i in range(self.n_atoms):
                self.atoms[i,:3] = np.dot(inv_lattice_vecs,self.atoms[i,:3].T)

    def calc_absolute_coordinates(self,repeat=[1,1,1]):
        n_repeat = repeat[0]*repeat[1]*repeat[2]

        abs_coord = np.zeros((self.n_atoms,repeat[0],repeat[1],repeat[2],4))

        for j1 in range(repeat[0]):
            for j2 in range(repeat[1]):
                for j3 in range(repeat[2]):
                    for i in range(self.n_atoms):
                        abs_coord[i,j1,j2,j3,:3] = np.dot(self.lattice_vectors.T,self.atoms[i,:3].T) + j3*self.lattice_vectors[2,:]+j2*self.lattice_vectors[1,:]+j1*self.lattice_vectors[0,:]
                        abs_coord[i,j1,j2,j3,3] = self.atoms[i,3]
                abs_coord_out = abs_coord.reshape((n_repeat*self.n_atoms,4))
        return abs_coord_out

    def find_bonds(self,abs_coords):
        n_atoms = abs_coords.shape[0]
        abs_coords_pure = abs_coords[:,:3]

        dist_mat = np.zeros((n_atoms,n_atoms))
        bonds = []
        for j1 in range(n_atoms):
            for j2 in range(j1+1,n_atoms):

                dist = np.linalg.norm(abs_coords_pure[j1,:]-abs_coords_pure[j2,:] )
                if dist < (cov_radii[int(abs_coords[j1,3])]+cov_radii[int(abs_coords[j2,3])])*1.3:
                    dist_mat[j1, j2] = dist
                    bonds.append([j1,j2]);
        return bonds

    def convert_to_tpiba(self,band_structure_points):
        if type(band_structure_points) in [list,tuple]:
            band_structure_points = np.array(band_structure_points)
        N = band_structure_points.shape[0]
        conv_points = np.zeros((N,3))
        a = np.linalg.norm(self.lattice_vectors[0, :])
        for i in range(N):
            conv_points[i,:] = np.dot(self.inv_lattice_vectors.T,band_structure_points[i,:])/(2*np.pi/a)
        return conv_points

class BandStructure:
    def __init__(self,bands,special_k_points=None,bs_type='electronic'):
        self.bands = bands
        self.bandgap,self.k_bandgap = self._find_bandgap(bands)
        self.special_k_points = special_k_points
        self.bs_type = bs_type

    def _find_bandgap(self, bands):
        for i in range(len(bands)):
            valence_band = bands[i]
            cond_band = bands[i + 1]
            if (np.max(cond_band[:, 1]) > 0) and (np.min(cond_band[:, 1]) < 0):
                return None, None
            if any(cond_band[:, 1] > 0):
                break
        # Direct bandgap
        band_diff = cond_band[:, 1] - valence_band[:, 1]
        bandgap_index = np.argmin(band_diff)
        bandgap = np.min(band_diff)
        k_bandgap = valence_band[bandgap_index, 0]
        # Indirect bandgap
        if np.abs((np.min(cond_band[:, 1]) - np.max(valence_band[:, 1])) - bandgap) > 0.01:
            bandgap = (np.min(cond_band[:, 1]) - np.max(valence_band[:, 1]))
            k_bandgap = None
        return bandgap, k_bandgap

class OpticalSpectrum:
    def __init__(self,energy,epsilon2,epsilon1=None):
        self.energy = energy # energy in eV

        if type(epsilon2) == list or type(epsilon2)== tuple:
            self.epsilon2_11 = epsilon2[0]
            self.epsilon2_22 = epsilon2[1]
            self.epsilon2_33 = epsilon2[2]
            self.epsilon2 = (self.epsilon2_11+self.epsilon2_22+self.epsilon2_33)/3
        else:
            self.epsilon2 = epsilon2

        if epsilon1 is not None and (type(epsilon1) == list or type(epsilon1)== tuple):
            self.epsilon1_11 = epsilon1[0]
            self.epsilon1_22 = epsilon1[1]
            self.epsilon1_33 = epsilon1[2]
            self.epsilon1 = (self.epsilon1_11 + self.epsilon1_22 + self.epsilon1_33) / 3
        else:
            self.epsilon1 = epsilon1

class StructureParser:
    def __init__(self):
        pass

    def parse_cif_file(self,filename):
        with open(filename, 'r') as f:
            cif_text = f.read()
        cif_text = cif_text.replace('\r','')
        alpha = float(re.findall(r"_cell_angle_alpha[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])
        beta = float(re.findall(r"_cell_angle_beta[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])
        gamma = float(re.findall(r"_cell_angle_gamma[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])
        a = float(re.findall(r"_cell_length_a[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])/bohr
        b = float(re.findall(r"_cell_length_b[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])/bohr
        c = float(re.findall(r"_cell_length_c[\s\t]*[-+]?\d*[\.\d+]?", cif_text)[0].split()[1])/bohr
        params = [a,b,c,alpha,beta,gamma]

        unit_vectors = np.array(calculate_lattice_vectors_from_parameters(params))


        atom_lines,start_of_frac = self.find_atom_lines(cif_text)

        n_atoms = len(atom_lines)
        atom_array = np.zeros((n_atoms,4))

        for i,atom_line in enumerate(atom_lines):
            atom_l = atom_line.split()
            species = atom_l[0]
            species = self.remove_numbers_from_string(species)
            species = species.title()

            x = atom_l[start_of_frac].split('(')[0]
            y = atom_l[start_of_frac+1].split('(')[0]
            z = atom_l[start_of_frac+2].split('(')[0]
            atom_array[i,:] = np.array([x,y,z,p_table_rev[species]])


        atom_array = atom_array[atom_array[:,3]!=0,:]
        sym_lines = find_lines_between(cif_text,'_symmetry_equiv_pos_as_xyz','loop_',strip=True)
        sym_lines = self.remove_cif_attributes(sym_lines)
        n_sym = len(sym_lines)
        sym_atom_array = np.zeros((n_atoms*n_sym,4))

        counter = 0
        if sym_lines[0][0].isdigit():
            sym_enumeration = True
        else:
            sym_enumeration = False

        for sym_line in sym_lines:
            if sym_enumeration:
                sym_line = self.remove_counter(sym_line)
            sym = sym_line.replace("'",'').split(',')
            for i in range(n_atoms):
                pos = atom_array[i,:3]
                atom_spec = atom_array[i,3]
                new_pos = self.perform_sym(pos,sym)
                sym_atom_array[counter,:3] = new_pos
                sym_atom_array[counter,3] = atom_spec
                counter +=1

        atom_array_finally = self.remove_duplicates_old(sym_atom_array)
        atom_array_finally_sorted = atom_array_finally[np.argsort(atom_array_finally[:,3]),:]
        return CrystalStructure(unit_vectors,atom_array_finally_sorted,scale=a)


    def remove_duplicates_old(self, data, treshold=0.01):
        if len(data) == 0:
            return np.array([])
        new_data = []
        n, m = data.shape
        for iii in range(n):

            tr_data = np.linalg.norm(data[iii + 1:, :] - data[iii, :], axis=1)
            if not any(tr_data < treshold):
                new_data.append(data[iii, :])
        return np.array(new_data)

    def perform_sym(self,pos,sym):
        x = pos[0]
        y = pos[1]
        z = pos[2]
        namespace = {'x':x,'y':y,'z':z}
        exec('xn = ' + sym[0],namespace)
        exec('yn = ' + sym[1],namespace)
        exec('zn = ' + sym[2],namespace)
        xn = namespace["xn"] % 1
        yn = namespace["yn"] % 1
        zn = namespace["zn"] % 1
        return np.array([xn,yn,zn])

    def remove_numbers_from_string(self,x):
        new_string = ''
        for i,el in enumerate(x):
            if not el.isalpha():
                break
            else:
                new_string += el
        return new_string

    def remove_counter(self,x):
        for i,el in enumerate(x):
            if not el.isdigit():
                break
        return x[i:]

    def find_atom_lines(self,text):
        text_lines = text.split('\n')
        text_lines = [x.strip() for x in text_lines]
        for i,line in enumerate(text_lines):
            if line == '_atom_site_fract_x':
                line_of_x = i
                break
        for i in range(1,line_of_x):
            back_line = text_lines[line_of_x-i]
            if back_line[0] != '_':
                start_of_block = line_of_x-i+1
                break
        number_of_other_lines = line_of_x - start_of_block
        atom_lines = []
        for line in text_lines[line_of_x:]:
            if len(line)==0 or line == 'loop_':
                break
            if line[0] == '_':
                continue
            else:
                atom_lines.append(line)
        return atom_lines,number_of_other_lines

    def remove_cif_attributes(self,text):
        res = []
        for line in text:
            if line[0] == '_':
                break
            else:
                res.append(line)
        return res


class GeneralHandler():
    def __init__(self):
        from exciting_handler import Handler
        self.exciting_handler = Handler()
        from quantum_espresso_handler import Handler
        self.quantum_espresso_handler = Handler()

        self.handlers = {'exciting':self.exciting_handler,'quantum espresso': self.quantum_espresso_handler}

    def is_handler_available(self,engine_name):
        handler = self.handlers[engine_name]

        if len(handler.dft_installation_folder) > 0:
            return True
        else:
            return False


    def parse_input_file(self,engine_name,filename):
        handler = self.handlers[engine_name]
        return handler.parse_input_file(filename)


class KohnShamDensity(object):
    def __init__(self,density):
        self.density = density

class MolecularDensity(object):
    def __init__(self,density,lattice_vecs,origin):
        self.density = density
        self.grid_vectors = lattice_vecs
        self.origin = origin

def calculate_lattice_vectors_from_parameters(parameters):
    a, b, c, alpha, beta, gamma = parameters
    alpha = alpha * np.pi / 180
    beta = beta * np.pi / 180
    gamma = gamma * np.pi / 180

    a1 = a * np.array([1, 0, 0])
    a2 = b * np.array([np.cos(gamma), np.sin(gamma), 0])
    x = np.cos(beta)
    y = (np.cos(alpha) - np.cos(beta) * np.cos(gamma)) / np.sin(gamma)
    z = np.sqrt(1 - x ** 2 - y ** 2)
    a3 = c * np.array([x, y, z])
    return a1, a2, a3

def find_lines_between(text,a,b,strip=False):
    reading = False
    atom_lines = []
    for line in text.split('\n'):
        if strip:
            line = line.strip()
        if line == a:
            reading = True
            continue
        elif reading and line == b:
            break
        if reading and len(line)>0:
            atom_lines.append(line)
    return atom_lines





if __name__ == "__main__":
    atoms = np.array([[0, 0, 0, 6], [0.25, 0.25, 0.25, 6]])
    unit_cell = 6.719 * np.array([[0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]])

    crystal_structure = CrystalStructure(unit_cell, atoms)
    coords = crystal_structure.calc_absolute_coordinates(repeat=[1,1,2])
    print(crystal_structure.find_bonds(coords))

    parser = StructureParser()
    out = parser.parse_cif_file('/home/jannick/OpenDFT_projects/LiBH4/1504402.cif')
    general_handler = GeneralHandler()
    # print(general_handler.available_handlers)