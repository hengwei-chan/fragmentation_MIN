import os
import sys
import numpy as np
from pyscf.geomopt.berny_solver import optimize
from berny import Berny, geomlib
from input_file import *
#from sow import *
import shutil
import nicolefragment
from nicolefragment import runpie, Molecule, fragmentation, Fragment, Pyscf, Psi4
import dill
import glob
import threading
import time

path = sys.argv[1]
folder = sys.argv[2]
queue = sys.argv[3]
coords_name = path.replace(".cml", ".xyz")

input_molecule = Molecule.Molecule(path, special_prim=atom, special_charge=charge, special_spin=spin)
input_molecule.initalize_molecule()
obj_list = []
name_list = []

if software == 'Pyscf':
    software = Pyscf.Pyscf

if software == 'Psi4':
    software = Psi4.Psi4
    
if mim_levels == 1:
    frag1 = fragmentation.Fragmentation(input_molecule)
    frag1.do_fragmentation(fragtype=frag_type, value=frag_deg)
    frag1.initalize_Frag_objects(theory=high_theory, basis=basis_set, qc_backend=software, xc=xc, step_size=stepsize, local_coeff=1)
    os.path.abspath(os.curdir)
    os.chdir(folder)
    level_list = os.listdir()
    for level in level_list:
        if os.path.isdir(os.path.join(level)):
            shutil.rmtree(level)
    os.mkdir('frag1')
    os.chdir('frag1')
    for i in range(0, len(frag1.frags)):
        filename = "fragment" + str(i) + ".dill"
        outfile = open(filename, "wb")
        print("writing object:", frag1.frags[i])
        dill.dump(frag1.frags[i], outfile)
        outfile.close()
    obj_list.append(frag1)
    name_list.append('frag1')
    os.chdir('../')
    
if mim_levels == 2:
    #""" MIM high theory, small fragments"""
    frag1 = fragmentation.Fragmentation(input_molecule)
    frag1.do_fragmentation(fragtype=frag_type, value=frag_deg)
    frag1.initalize_Frag_objects(theory=high_theory, basis=basis_set, qc_backend=software, xc=xc, step_size=stepsize, local_coeff=1)
    os.path.abspath(os.curdir)
    os.chdir(folder)
    level_list = os.listdir()
    for level in level_list:
        if os.path.isdir(os.path.join(level)):
            shutil.rmtree(level)
    os.mkdir('frag1')
    os.chdir('frag1')
    for i in range(0, len(frag1.frags)):
        filename = "fragment" + str(i) + ".dill"
        outfile = open(filename, "wb")
        dill.dump(frag1.frags[i], outfile)
        outfile.close()
    obj_list.append(frag1)
    name_list.append('frag1')
    os.chdir('../')
    
    #""" MIM low theory, small fragments"""
    frag2 = fragmentation.Fragmentation(input_molecule)
    frag2.do_fragmentation(fragtype=frag_type, value=frag_deg)
    frag2.initalize_Frag_objects(theory=low_theory, basis=basis_set, qc_backend=software, xc=xc, step_size=stepsize, local_coeff=-1)
    os.mkdir('frag2')
    os.chdir('frag2')
    for i in range(0, len(frag2.frags)):
        filename = "fragment" + str(i) + ".dill"
        outfile = open(filename, "wb")
        dill.dump(frag2.frags[i], outfile)
        outfile.close()
    obj_list.append(frag2)
    name_list.append('frag2')
    os.chdir('../')
    
    #""" MIM low theory, large fragments (iniffloate system)"""
    frag3 = fragmentation.Fragmentation(input_molecule)
    frag3.do_fragmentation(fragtype=frag_type, value=frag_deg_large)
    frag3.initalize_Frag_objects(theory=low_theory, basis=basis_set, qc_backend=software, xc=xc, step_size=stepsize, local_coeff=1)
    os.mkdir('frag3')
    os.chdir('frag3')
    for i in range(0, len(frag3.frags)):
        filename = "fragment" + str(i) + ".dill"
        outfile = open(filename, "wb")
        dill.dump(frag3.frags[i], outfile)
        outfile.close()
    obj_list.append(frag3)
    name_list.append('frag3')
    os.chdir('../')

os.chdir('../')


def opt_fnc(newcoords, cycle):
    os.chdir(folder)
    for atom in range(0, len(newcoords)): #makes newcoords = self.molecule.atomtable
        x = list(newcoords[atom])
        obj_list[0].molecule.atomtable[atom][1:] = x
    
    for j in range(0, len(obj_list)):       #update the other frag instances if MIM2 or higher level
        obj_list[j].molecule.atomtable = obj_list[0].molecule.atomtable
        os.chdir(name_list[j])

        #remove old status
        status_list = glob.glob('*.status')
        for filename in status_list:
            os.remove(filename)

        #repickle fragment instances with new coords
        for i in range(0, len(obj_list[j].frags)):
            filename = "fragment" + str(i) + ".dill"
            if cycle == 0:
                outfile = open(filename, "wb")
                dill.dump(obj_list[j].frags[i], outfile)
                outfile.close()

            if cycle > 0:
                infile = open(filename, "rb")
                new_instance = dill.load(infile)
                new_instance.molecule.atomtable = obj_list[0].molecule.atomtable
                outfile = open(filename, "wb")
                dill.dump(new_instance, outfile)
                infile.close()
                outfile.close()
        os.chdir('../')
    
    print("Removing old energy.npy and grad.npy")
    npy_list = glob.glob('*.npy')
    for thing in npy_list:
        os.remove(thing)
    os.chdir('../')

    path = os.getcwd() + "/" + folder

    if queue == 'pbs':
        cmd = "python batch.py %s %s pbs.sh %s"%(str(batch_size), folder, queue)       ##For Newriver
        opt_cmd = 'qsub -N checker -v FOLDER="%s" geom_opt.sh'%(path)
    
    if queue == 'slurm':
        cmd = 'python batch.py %s %s slurm_pbs.sh %s'%(str(batch_size), folder, queue)         ##For TinkerCliffs/Huckleberry/Infer
        opt_cmd = 'sbatch -e %s -J checker -o "%s" --export=FOLDER="%s" slurm_geom_opt.sh'%(os.getcwd()+"/checker.error", os.getcwd() + "checker.out", path)

    if queue == 'local':
        cmd = 'python batch.py %s %s run.py %s'%(str(batch_size), folder, queue)
        opt_cmd = 'pwd'
    
    print(cmd)
    print(opt_cmd)
    os.system(cmd)
    os.system(opt_cmd)
    etot = 0
    gtot = 0

    os.chdir(folder)
    #pauses python function until all batches are done running and global etot and gtot calculated
    while len(glob.glob("*.npy")) < 2:
        print("sleeping in while loop in opt_fnc in opt.py")
        time.sleep(30)
        print("done sleeping")
        pass

    #load in the etot and gtot
    etot = np.load('energy.npy')
    gtot = np.load('gradient.npy')
    print("energy from .npy = ", etot)
    os.chdir('../')
    return etot, gtot


obj_list[0].write_xyz(coords_name)
os.path.abspath(os.curdir)
optimizer = Berny(geomlib.readfile(os.path.abspath(coords_name)), debug=True)
count = 0
etot_opt = 0
grad_opt = 0
for geom in optimizer:
    print("\n opt cycle:", count, "\n")
    solver = opt_fnc(geom.coords, count)
    count = count+1
    optimizer.send(solver)
    etot_opt = solver[0]
    grad_opt = solver[1]
relaxed = geom

print("\n", "##########################", '\n', "#       Converged!       #", '\n', "##########################") 
print('\n', "Energy = ", etot_opt)
print('\n', "Converged_Gradient:", "\n", grad_opt)

print("\n", relaxed.coords, "\n")
os.chdir(folder)

#updating coords with optimized geometry for hessian
for atom in range(0, len(relaxed.coords)): #makes newcoords = self.molecule.atomtable
    x = list(relaxed.coords[atom])
    obj_list[0].molecule.atomtable[atom][1:] = x

for j in range(0, len(obj_list)):       #update the other frag instances if MIM2 or higher level
    obj_list[j].molecule.atomtable = obj_list[0].molecule.atomtable
    os.chdir(name_list[j])

    #remove old pickled objects and status
    #for filename in os.listdir():
    #    os.remove(filename)

    #repickle fragment instances with new coords
    for i in range(0, len(obj_list[j].frags)):
        filename = "fragment" + str(i) + ".dill"
        outfile = open(filename, "wb")
        dill.dump(obj_list[j].frags[i], outfile)
        outfile.close()
    os.chdir('../')
os.chdir('../')

#Running hessian and apt at optimized geometry
if queue == 'pbs':
    cmd = "python batch.py %s %s hess_apt.sh %s"%(str(batch_size), folder, queue)       ##For Newriver

if queue == 'slurm':
    cmd = 'python batch.py %s %s slurm_hess_apt.sh %s'%(str(batch_size), folder, queue)         ##For TinkerCliffs/Huckleberry/Infer

if queue == 'local':
    cmd = 'python batch.py %s %s run_opt.py %s'%(str(batch_size), folder, queue)

print(cmd)
os.system(cmd)




