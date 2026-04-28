const fs = require('fs');

const dataFile = '/home/uara/Work/gokhale_familytree/data/family-tree.from-html.js';
const content = fs.readFileSync(dataFile, 'utf8');
const jsonString = content.substring(content.indexOf('{'), content.lastIndexOf('}') + 1);
const data = JSON.parse(jsonString);

const cityMap = [
    { name: 'Madan Gokhale', city: 'Pune', scope: 'descendants' },
    { name: 'Vallari', city: 'Pune', scope: 'descendants' },
    { name: 'Pradnya', city: 'Pune', scope: 'descendants' },
    { name: 'Vaishali S Tamhankar', city: 'Pune', scope: 'descendants' },
    { name: 'Arvind R Deodhar', city: 'Pune', scope: 'descendants' },
    { name: 'Vasanti K Gokhale', city: 'Thane, Mumbai', scope: 'descendants' },
    { name: 'Koustubh V Gokhale', city: 'Vashi, Mumbai', scope: 'descendants' },
    { name: 'Shilpa Sachin Kelkar', city: 'Sydney, Australia', scope: 'descendants' },
    { name: 'Girish Dinkar Gokhale', city: 'Hubli', scope: 'descendants' },
    { name: 'Padmaja (Asha)', city: 'Nagar', scope: 'husband' },
    { name: 'Pallavi Sidharth', city: 'Banglore', scope: 'descendants' },
    { name: 'Asavari (Sunanda)', city: 'Sangli', scope: 'descendants' },
    { name: 'Sunita Mohan Bhave', city: 'Ratnagiri, Konkan', scope: 'family_unit' },
];

const peopleById = new Map(data.people.map(p => [p.id, p]));
const familiesByMember = new Map();
data.families.forEach(f => {
    f.memberIds.forEach(mId => {
        if (!familiesByMember.has(mId)) familiesByMember.set(mId, []);
        familiesByMember.get(mId).push(f);
    });
});

const familiesById = new Map(data.families.map(f => [f.id, f]));

function getDescendants(personId) {
    const descendants = new Set();
    const stack = [personId];
    while (stack.length > 0) {
        const pId = stack.pop();
        if (descendants.has(pId)) continue;
        descendants.add(pId);
        
        // Find families where this person is a member
        const families = familiesByMember.get(pId) || [];
        families.forEach(f => {
            // Add other members of the family (spouses)
            f.memberIds.forEach(mId => descendants.add(mId));
            
            // Add children of this family
            f.childFamilyIds.forEach(cfId => {
                const cf = familiesById.get(cfId);
                if (cf) {
                    cf.memberIds.forEach(mId => stack.push(mId));
                }
            });
        });
    }
    return descendants;
}

function getHusband(personId) {
    const result = new Set([personId]);
    const families = familiesByMember.get(personId) || [];
    families.forEach(f => {
        f.memberIds.forEach(mId => result.add(mId));
    });
    return result;
}

function getFamilyUnit(personId) {
    const result = new Set([personId]);
    const families = familiesByMember.get(personId) || [];
    families.forEach(f => {
        f.memberIds.forEach(mId => result.add(mId));
        // Add children
        f.childFamilyIds.forEach(cfId => {
            const cf = familiesById.get(cfId);
            if (cf) {
                cf.memberIds.forEach(mId => result.add(mId));
            }
        });
    });
    return result;
}

cityMap.forEach(entry => {
    const person = data.people.find(p => p.name.includes(entry.name));
    if (!person) {
        console.log(`Could not find person: ${entry.name}`);
        return;
    }
    
    let affectedIds;
    if (entry.scope === 'descendants') {
        affectedIds = getDescendants(person.id);
    } else if (entry.scope === 'husband') {
        affectedIds = getHusband(person.id);
    } else if (entry.scope === 'family_unit') {
        affectedIds = getFamilyUnit(person.id);
    }
    
    affectedIds.forEach(id => {
        const p = peopleById.get(id);
        if (p && !p.name.toLowerCase().startsWith('late')) {
            p.city = entry.city;
        }
    });
});

fs.writeFileSync(dataFile, `window.familyTreeData = ${JSON.stringify(data, null, 2)};`);
console.log('Successfully updated family tree data with cities.');
